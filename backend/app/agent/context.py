from dataclasses import dataclass


@dataclass
class AgentContext:
    """
    Per-invocation context passed to the agent via context=, injected
    into tools through ToolRuntime -- hidden from the LLM's tool schema
    entirely, and (unlike a bare contextvar) reliably propagates across
    LangGraph's internal thread-pool execution of sync tools.
    """
    github_token: str | None = None
