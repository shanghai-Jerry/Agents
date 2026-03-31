"""Shared tools package.

Provides reusable tools that can be included in any sub-agent's tool set.
All tools are registered with the global ResourceRegistry on import.
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
    if name == "sandbox_exec":
        from tools.sandbox import sandbox_exec
        return sandbox_exec
    if name == "sandbox_upload":
        from tools.sandbox import sandbox_upload
        return sandbox_upload
    if name == "sandbox_download":
        from tools.sandbox import sandbox_download
        return sandbox_download
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
