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
        async for message_chunk, metadata in agent.astream(
            {"messages": [{"role": "user", "content": message}]},
            config=config,
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
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
            # streaming version:
            yield "\n\n[The AI provider's rate limit was hit. Please try again shortly.]"

