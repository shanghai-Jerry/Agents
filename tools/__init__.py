"""Shared tools package.

Provides reusable tools that can be included in any sub-agent's tool set.
"""

from tools.thinking import think_tool
from tools.utils import fetch_webpage_content

__all__ = [
    "think_tool",
    "fetch_webpage_content",
]


def __getattr__(name: str):
    """Lazy import for optional tools to avoid import errors when deps are missing."""
    if name == "tavily_search":
        from tools.search import tavily_search
        return tavily_search
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
