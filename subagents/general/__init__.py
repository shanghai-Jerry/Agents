"""General-purpose sub-agent.

A versatile sub-agent that can handle a wide range of tasks.
Serves as the default fallback when no specialized sub-agent is available.
"""

from subagents.general.prompts import GENERAL_INSTRUCTIONS
from subagents.general.tools import get_default_tools

__all__ = [
    "GENERAL_INSTRUCTIONS",
    "get_default_tools",
]


def create_general_subagent(tools: list | None = None) -> dict:
    """Create the general sub-agent configuration dictionary.

    This returns a dictionary in the format expected by ``create_deep_agent``'s
    ``subagents`` parameter.

    Args:
        tools: Additional tools beyond the defaults.
            If ``None``, uses the default tool set from ResourceRegistry.
            Note: The permission system will further filter this list based
            on ``permissions.yaml``.

    Returns:
        A dictionary with ``name``, ``description``, ``system_prompt``, and ``tools``.
    """
    from datetime import datetime

    all_tools = get_default_tools()
    if tools:
        all_tools.extend(tools)

    current_date = datetime.now().strftime("%Y-%m-%d")

    return {
        "name": "general",
        "description": (
            "A general-purpose assistant that can handle a wide variety of tasks "
            "including research, analysis, writing, and problem-solving. "
            "Use this agent for requests that don't match a more specialized sub-agent."
        ),
        "system_prompt": GENERAL_INSTRUCTIONS.format(date=current_date),
        "tools": all_tools,
    }
