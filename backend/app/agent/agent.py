import re
import asyncio
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app.agent.context import AgentContext
from app.agent.tools import search_codebase, get_file, list_good_first_issues, get_directory_structure
from app.core.config import settings
from app.core.llm import get_chat_model

_model = ChatGoogleGenerativeAI(
    model=settings.google_model_name,
    api_key=settings.google_api_key,
)

_checkpointer_cm = None
_agent = None

_REPO_CONTEXT_PREFIX = re.compile(r"^\[Repository repo_id: [^\]]+\]\n")

SYSTEM_PROMPT = """You are RepoSage, an assistant that helps users understand a GitHub repository.

Tool selection:
- Use get_file when the user asks to explain, review, walk through, or see the code of a
  specific named file. It returns the full file content, giving you enough context for a
  real, detailed explanation -- not just a fragment.
- Use search_codebase to locate relevant code across the repo, or for broader conceptual
  questions where you don't know the exact file up front.
- You can chain them: search_codebase to find the right file, then get_file to read it in
  full before answering.
- Use get_directory_structure when the user asks about the repo's organization, folder
  layout, or "what modules exist" -- search_codebase returns fragments and can't answer
  holistic structural questions well.
  
When explaining code:
- Go beyond a one-paragraph summary -- walk through the actual logic: what each function
  does, key control flow, notable design choices.
- When asked to cite, show, or quote code, include real excerpts in fenced code blocks
  (```python ... ```), not just a prose description.
- Cite file paths in backticks when referencing them, but don't repeat "as seen in X file"
  after every sentence. Cite naturally, once per relevant claim.

Formatting:
- Use proper Markdown: bullet lists (- item) for enumerations, fenced code blocks (```)
  for directory trees, file structure, or any code -- never plain unformatted text for
  these.

Accuracy:
- Never state specific technology choices (databases, libraries, frameworks) unless you
  have actually confirmed them via search_codebase or get_file in this conversation.
  If you haven't verified something specific, say so or use a tool to check first,
  rather than guessing based on what's typical for a similar-sounding project.
- Never fabricate code examples. Only show code you've actually retrieved via get_file
  or search_codebase -- if you want to illustrate usage and don't have a real example
  retrieved, say that clearly rather than inventing one that looks plausible.

You have full access to this conversation's history in your context. Never claim you can't
recall earlier turns -- answer directly from the conversation above you.

"""


_model = get_chat_model()

async def init_agent():
    """
    Async setup for the Redis-backed checkpointer. Must run inside a
    running event loop (FastAPI's lifespan startup), not at plain module
    import time -- AsyncRedisSaver.asetup() is a coroutine, and there's
    no event loop available yet during a bare `import agent.py`.
    """
    global _checkpointer_cm, _agent

    _checkpointer_cm = AsyncRedisSaver.from_conn_string(settings.redis_url)
    checkpointer = await _checkpointer_cm.__aenter__()
    await checkpointer.asetup()

    _agent = create_agent(
        model=_model,
        tools=[search_codebase, get_file, list_good_first_issues, get_directory_structure],
        checkpointer=checkpointer,
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
    )


async def close_agent():
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized -- init_agent() must run during app startup")
    return _agent


async def chat(message: str, thread_id: str, github_token: str | None = None, max_retries: int = 2) -> str:
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    context = AgentContext(github_token=github_token)

    result = None
    for attempt in range(max_retries + 1):
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                context=context,
            )
            break
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(s in error_str for s in ("429", "rate limit", "quota", "resource_exhausted"))

            if attempt == max_retries:
                # Last attempt failed -- always return a clean message here,
                # never fall through with result still unset.
                if is_rate_limit:
                    return "The AI provider's free-tier quota is temporarily exhausted. Please try again shortly."
                return "Something went wrong while generating a response. Please try again."

            await asyncio.sleep(5 * (attempt + 1) if is_rate_limit else 1)

    final_message = result["messages"][-1]
    content = final_message.content
    if isinstance(content, str):
        return content
    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(text_parts)


async def chat_stream(message: str, thread_id: str, github_token: str | None = None, max_retries: int = 2):
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    context = AgentContext(github_token=github_token)

    for attempt in range(max_retries + 1):
        try:
            async for message_chunk, metadata in agent.astream(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
                context=context,
                stream_mode="messages",
            ):
                if metadata.get("langgraph_node") != "model":
                    continue
                content = message_chunk.content
                if isinstance(content, str):
                    if content:
                        yield content
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                yield text
            return  # streamed successfully, we're done
        except Exception as e:
            error_str = str(e).lower()
            is_rate_limit = any(s in error_str for s in ("429", "rate limit", "quota", "resource_exhausted"))

            if attempt == max_retries:
                if is_rate_limit:
                    yield "\n\n[The AI provider's free-tier quota is temporarily exhausted. Please try again shortly.]"
                else:
                    yield "\n\n[Something went wrong while generating a response. Please try again.]"
                return

            await asyncio.sleep(5 * (attempt + 1) if is_rate_limit else 1)

async def get_history(thread_id: str) -> list[dict]:
    """
    Retrieves prior messages for a thread from the checkpointer's state,
    so the frontend can restore a conversation on mount instead of always
    starting blank. Filters to Human/AI turns meant for display -- tool
    call/result messages are implementation detail, not something a user
    should see re-rendered as a chat bubble.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}
    state = await agent.aget_state(config)

    if not state or not state.values.get("messages"):
        return []

    history = []
    for msg in state.values["messages"]:
        msg_type = msg.__class__.__name__
        if msg_type == "HumanMessage" and isinstance(msg.content, str) and msg.content:
            display_text = _REPO_CONTEXT_PREFIX.sub("", msg.content)
            if display_text:
                history.append({"who": "you", "text": display_text})
        elif msg_type == "AIMessage":
            content = msg.content
            if isinstance(content, str) and content:
                history.append({"who": "agent", "text": content})
            elif isinstance(content, list):
                text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                if text:
                    history.append({"who": "agent", "text": text})
        # ToolMessage and empty tool-call-only AIMessages are intentionally skipped

    return history


async def generate_title(message: str) -> str:
    try:
        response = await _model.ainvoke([
            {"role": "system", "content": "Generate a short chat title (max 6 words, no quotes or punctuation) summarizing the user's question."},
            {"role": "user", "content": message},
        ])
        content = response.content
        if isinstance(content, list):
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        return content.strip()[:60] or "New chat"
    except Exception:
        return message[:40]  # fallback: just truncate rather than fail the whole flow
