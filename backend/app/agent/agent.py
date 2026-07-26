import re
import asyncio
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app.agent.tools import search_codebase, get_file, list_good_first_issues
from app.core.config import settings

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

When explaining code:
- Go beyond a one-paragraph summary -- walk through the actual logic: what each function
  does, key control flow, notable design choices.
- When asked to cite, show, or quote code, include real excerpts in fenced code blocks
  (```python ... ```), not just a prose description.
- Cite file paths in backticks when referencing them, but don't repeat "as seen in X file"
  after every sentence. Cite naturally, once per relevant claim.

You have full access to this conversation's history in your context. Never claim you can't
recall earlier turns -- answer directly from the conversation above you."""


def _get_model():
    if settings.llm_provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.groq_model_name, api_key=settings.groq_api_key)
    else:
        return ChatGoogleGenerativeAI(model=settings.google_model_name, api_key=settings.google_api_key)

_model = _get_model()

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
        tools=[search_codebase, get_file, list_good_first_issues],
        checkpointer=checkpointer,
        system_prompt=SYSTEM_PROMPT,
    )


async def close_agent():
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)


def get_agent():
    if _agent is None:
        raise RuntimeError("Agent not initialized -- init_agent() must run during app startup")
    return _agent


async def chat(message: str, thread_id: str, max_retries: int = 2) -> str:
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    for attempt in range(max_retries + 1):
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
            )
            break
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                return "The AI provider's free-tier quota is temporarily exhausted. Please try again shortly."
            await asyncio.sleep(5 * (attempt + 1))

    final_message = result["messages"][-1]
    content = final_message.content
    if isinstance(content, str):
        return content
    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(text_parts)


async def chat_stream(message: str, thread_id: str):
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # print("Starting stream")

        async for message_chunk, metadata in agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
            stream_mode="messages",
        ):
            # print("Received chunk")
            # print(metadata)
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
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
            # streaming version:
            yield "\n\n[The AI provider's rate limit was hit. Please try again shortly.]"

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
