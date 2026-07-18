import asyncio
from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from google.api_core.exceptions import ResourceExhausted

from app.agent.tools import search_codebase, get_file, list_good_first_issues
from app.core.config import settings

_model = ChatGoogleGenerativeAI(
    model=settings.google_model_name,
    api_key=settings.google_api_key,
)

_checkpointer_cm = None
_agent = None


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
        except ResourceExhausted:
            if attempt == max_retries:
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
    except ResourceExhausted:
        yield "\n\n[The AI provider's free-tier quota is temporarily exhausted. Please try again shortly.]"
