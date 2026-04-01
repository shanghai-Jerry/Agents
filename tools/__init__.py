"""Shared tools package.

Provides reusable tools that can be included in any sub-agent's tool set.
All tools are registered with the global ResourceRegistry on import.

Tool registration is split into two phases:
- **Core tools** (no extra deps): imported eagerly when this package is loaded.
- **Optional tools** (require third-party deps): imported on demand via
  :func:`import_optional_tools`, with graceful degradation on missing deps.

Usage::

    import tools                # registers core tools only
    tools.import_optional_tools()  # additionally registers tavily, sandbox, etc.

    from agents.resources import resource_registry
    resource_registry.summary()    # see all registered tools
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core tools — no external dependencies beyond langchain_core
# ---------------------------------------------------------------------------

from tools.thinking import think_tool  # noqa: F401
from tools.fetch_webpage_content import fetch_webpage_content  # noqa: F401

__all__ = [
    "think_tool",
    "fetch_webpage_content",
    "import_optional_tools",
]

# ---------------------------------------------------------------------------
# Optional tools — require third-party packages
# ---------------------------------------------------------------------------

_optional_imported = False


def import_optional_tools() -> list[str]:
    """Import and register optional tools that require third-party packages.

    Each import is wrapped in a try/except so that missing dependencies
    are handled gracefully (logged as warning, tool not registered).

    Returns:
        List of tool names that were successfully registered.
    """
    global _optional_imported

    if _optional_imported:
        logger.debug("Optional tools already imported, skipping.")
        return []

    registered: list[str] = []

    # --- Tavily search ---
    try:
        from tools.search import tavily_search  # noqa: F401

        registered.append("tavily_search")
    except ImportError as e:
        logger.warning(
            "Optional tool 'tavily_search' not available: %s. "
            "Install with: pip install tavily-python",
            e,
        )

    # --- Modal sandbox ---
    try:
        from tools.sandbox import (  # noqa: F401
            sandbox_exec,
            sandbox_download,
            sandbox_upload,
        )

        registered.extend(["sandbox_exec", "sandbox_upload", "sandbox_download"])
    except ImportError as e:
        logger.warning(
            "Optional sandbox tools not available: %s. "
            "Install with: pip install modal",
            e,
        )

    _optional_imported = True

    if registered:
        logger.info(
            "Optional tools registered: %s",
            ", ".join(registered),
        )

    return registered
