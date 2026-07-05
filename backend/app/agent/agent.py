from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from app.agent.tools import search_codebase, get_file, list_good_first_issues
from app.core.config import settings

# InMemorySaver keeps conversation history in this process's memory only --
# fine for a single-instance dev/demo deployment, but history is lost on
# restart and isn't shared across multiple worker processes. Worth a
# README note as a known limitation; a persistent checkpointer (e.g.
# backed by Redis or Postgres) would be the production fix.
_checkpointer = InMemorySaver()

# Explicit model instantiation, not the "google_genai:model-name" string
# shorthand. The shorthand relies on os.environ["GOOGLE_API_KEY"] being
# set directly -- our Settings object loads .env into a Python attribute,
# which is a separate thing from process env vars, so the shorthand can't
# see it. Passing api_key= explicitly keeps this consistent with how the
# rest of the app (DB, JWT secret) sources config from Settings.
_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
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


def chat(message: str, thread_id: str) -> str:
    """
    Runs one turn of conversation against the agent, scoped to thread_id.
    Returns plain text, extracting it from the typed content blocks
    Gemini returns rather than handing the raw block structure up to
    callers like the API layer.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config=config,
    )

    final_message = result["messages"][-1]
    content = final_message.content

    if isinstance(content, str):
        return content

    text_parts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(text_parts)
