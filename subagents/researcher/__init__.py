"""Research sub-agent.

A specialized sub-agent for web research tasks. Uses Tavily for web search
and follows a structured research methodology.
"""

from subagents.researcher.prompts import RESEARCHER_INSTRUCTIONS
from subagents.researcher.tools import tavily_search, think_tool

__all__ = [
    "RESEARCHER_INSTRUCTIONS",
    "tavily_search",
    "think_tool",
]


def create_researcher_subagent(
    model: str | None = None,
    max_results: int = 10,
    search_depth: str = "advanced",
) -> dict:
    """Create the research sub-agent configuration dictionary.

    This returns a dictionary in the format expected by ``create_deep_agent``'s
    ``subagents`` parameter.

    Args:
        model: Optional model override for this sub-agent. If None, uses
            the orchestrator's subagent model.
        max_results: Maximum search results per query (default: 10).
        search_depth: Default search depth ("basic" or "advanced").

    Returns:
        A dictionary with ``name``, ``description``, ``system_prompt``, and ``tools``.
    """
    from datetime import datetime

    current_date = datetime.now().strftime("%Y-%m-%d")

    config: dict = {
        "name": "research-agent",
        "description": (
            "Delegate research tasks to this specialist. "
            "It searches the web, synthesizes findings, and produces comprehensive research summaries. "
            "Only give this researcher one topic at a time."
        ),
        "system_prompt": RESEARCHER_INSTRUCTIONS.format(date=current_date),
        "tools": [tavily_search, think_tool],
    }

    if model:
        config["model"] = model

    return config
