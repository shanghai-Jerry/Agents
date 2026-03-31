"""Sub-agents package.

Each sub-agent is defined in its own subdirectory under this package.
Sub-agents are registered with the ``AgentRegistry`` in ``agent.py``.
"""

from subagents.general import create_general_subagent

__all__ = [
    "create_general_subagent",
]
