"""Tools for the coder sub-agent.

Provides tool references for the coder agent. Tools are sourced from the
global ResourceRegistry and will be further filtered by the permission system
at registration time.
"""

# Import triggers @register_tool decorator registration
import tools.thinking  # noqa: F401

from agents.resources import resource_registry


def get_default_tools() -> list:
    """Get the default tool set for the coder agent.

    These tools serve as the initial set before permission filtering.
    The permission system will override this list based on permissions.yaml.

    Returns:
        List of LangChain BaseTool instances.
    """
    default_tool_names = [
        "think_tool",
        "sandbox_exec",
        "sandbox_upload",
        "sandbox_download",
    ]
    result = []
    for name in default_tool_names:
        instance = resource_registry.get_tool_instance(name)
        if instance is not None:
            result.append(instance)
    return result


__all__ = ["get_default_tools"]
