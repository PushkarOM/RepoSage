from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.redis import RedisSaver

from app.agent.tools import search_codebase, get_file, list_good_first_issues
from app.core.config import settings

import time
from google.api_core.exceptions import ResourceExhausted

# Redis-backed checkpointer used to persist conversation state across
# application restarts and multiple worker processes. Call `setup()` once
# during initialization to ensure the required Redis structures are ready.
_checkpointer = RedisSaver(settings.redis_url)
_checkpointer.setup()

# Explicit model instantiation, not the "google_genai:model-name" string
# shorthand. The shorthand relies on os.environ["GOOGLE_API_KEY"] being
# set directly -- our Settings object loads .env into a Python attribute,
# which is a separate thing from process env vars, so the shorthand can't
# see it. Passing api_key= explicitly keeps this consistent with how the
# rest of the app (DB, JWT secret) sources config from Settings.
_model = ChatGoogleGenerativeAI(
    model=settings.google_model_name,
    api_key=settings.google_api_key,
)

_agent = create_agent(
    model=_model,
    tools=[search_codebase, get_file, list_good_first_issues],
    checkpointer=_checkpointer,
)

def get_agent():
    """
    Returns the shared agent instance. A single module-level agent is
    reused across requests rather than rebuilt per call -- the
    checkpointer's conversation history lives on this instance, so
    recreating it per-request would silently break memory.
    """
    return _agent


def chat(message: str, thread_id: str, max_retries: int = 2) -> str:
    """
    Runs one turn of conversation against the agent, scoped to thread_id.
    Returns plain text, extracting it from the typed content blocks
    Gemini returns rather than handing the raw block structure up to
    callers like the API layer.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    for attempt in range(max_retries + 1):
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": message}]},
                config=config,
            )
            break
        except ResourceExhausted:
            if attempt == max_retries:
                return "The AI provider's free-tier quota is temporarily exhausted. Please try again shortly."
            time.sleep(5 * (attempt + 1))  # brief backoff, not a full exponential scheme -- fine at this scale

    final_message = result["messages"][-1]
    content = final_message.content

    if isinstance(content, str):
        return content

    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(text_parts)
