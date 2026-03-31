"""Coder sub-agent.

A specialized sub-agent for software engineering tasks. Uses Modal sandbox
for isolated code execution, supporting writing, running, debugging, and
testing code in a secure environment.
"""

from subagents.coder.prompts import CODER_INSTRUCTIONS
from subagents.coder.tools import get_default_tools

__all__ = [
    "CODER_INSTRUCTIONS",
    "get_default_tools",
]


def create_coder_subagent(
    model: str | None = None,
) -> dict:
    """Create the coder sub-agent configuration dictionary.

    This returns a dictionary in the format expected by ``create_deep_agent``'s
    ``subagents`` parameter.

    Args:
        model: Optional model override for this sub-agent. If None, uses
            the orchestrator's subagent model.

    Returns:
        A dictionary with ``name``, ``description``, ``system_prompt``, and ``tools``.
    """
    from datetime import datetime

    current_date = datetime.now().strftime("%Y-%m-%d")

    config: dict = {
        "name": "coder",
        "description": (
            "Delegate coding and development tasks to this specialist. "
            "It writes, executes, debugs, and tests code in an isolated Modal sandbox. "
            "Supports Python and other languages. "
            "Use for: writing code, debugging, running scripts, data processing, "
            "and any task that requires code execution."
        ),
        "system_prompt": CODER_INSTRUCTIONS.format(date=current_date),
        "tools": get_default_tools(),
    }

    if model:
        config["model"] = model

    return config
