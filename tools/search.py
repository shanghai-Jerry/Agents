"""Tavily web search tool.

Provides web search capabilities using the Tavily API.
Requires TAVILY_API_KEY environment variable.
"""

from __future__ import annotations

import os
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Check if Tavily is available
try:
    from tavily import TavilyClient
    _TAVILY_AVAILABLE = True
except ImportError:
    _TAVILY_AVAILABLE = False
    logger.warning(
        "tavily-python package not installed. "
        "Install with: pip install tavily-python"
    )


def _get_tavily_client() -> TavilyClient:
    """Get or create a Tavily client instance."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY environment variable is required. "
            "Get one at https://tavily.com/"
        )
    return TavilyClient(api_key=api_key)


@tool(parse_docstring=True)
def tavily_search(query: str, max_results: int = 10, search_depth: str = "basic") -> str:
    """Search the web using Tavily to find up-to-date information.

    Use this tool when you need to find current information, facts, or data
    from the internet. Good for research, fact-checking, and gathering context.

    Args:
        query: The search query string. Be specific and descriptive.
        max_results: Maximum number of results to return (default: 10, max: 20).
        search_depth: Search depth - "basic" for quick results, "advanced" for
            more thorough research (slower but higher quality).

    Returns:
        A formatted string with search results including titles, URLs, and content snippets.
    """
    if not _TAVILY_AVAILABLE:
        return (
            "Error: tavily-python package is not installed. "
            "Install it with: pip install tavily-python"
        )

    client = _get_tavily_client()

    try:
        response = client.search(
            query=query,
            max_results=min(max_results, 20),
            search_depth=search_depth,
            include_answer=True,
        )

        # Format results
        parts: list[str] = []

        # Include AI-generated answer if available
        if response.get("answer"):
            parts.append(f"## AI Answer\n{response['answer']}\n")

        # Format search results
        results = response.get("results", [])
        if results:
            parts.append(f"## Search Results ({len(results)} found)\n")
            for i, r in enumerate(results, 1):
                title = r.get("title", "Untitled")
                url = r.get("url", "")
                content = r.get("content", "No content available")
                score = r.get("score", 0)
                parts.append(f"### {i}. {title}")
                parts.append(f"**URL:** {url}")
                parts.append(f"**Relevance:** {score:.2f}")
                parts.append(f"{content}\n")
        else:
            parts.append("No results found for this query.")

        return "\n".join(parts)

    except Exception as e:
        return f"Error during Tavily search: {e}"


__all__ = ["tavily_search"]
