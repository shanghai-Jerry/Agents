"""Research sub-agent tools.

Imports shared tools for use by the research sub-agent.
"""

from tools.thinking import think_tool

__all__ = ["think_tool"]


def __getattr__(name: str):
    """Lazy import for tavily_search to avoid import errors when deps are missing."""
    if name == "tavily_search":
        from tools.search import tavily_search
        return tavily_search
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
