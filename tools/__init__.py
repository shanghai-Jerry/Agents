"""Shared tools package.

Provides reusable tools that can be included in any sub-agent's tool set.
"""

from tools.thinking import think_tool
from tools.utils import fetch_webpage_content

__all__ = [
    "think_tool",
    "fetch_webpage_content",
]
