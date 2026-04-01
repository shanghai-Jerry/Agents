"""Tools for the general-purpose sub-agent.

Returns all registered tools from the global ResourceRegistry.  The actual
capability boundary is defined solely by ``permissions.yaml`` — the permission
system filters this full list at registration time.
"""

import tools  # noqa: F401 — trigger core tool registration (optional tools registered by agent.py)
from agents.resources import resource_registry


def get_default_tools() -> list:
    """Return the complete set of registered tool instances.

    The permission system (permissions.yaml) is the single source of truth
    for which tools this agent may actually use.

    Returns:
        List of all LangChain BaseTool instances in the registry.
    """
    return resource_registry.all_tool_instances()


__all__ = ["get_default_tools"]
