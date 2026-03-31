"""Utility helpers for tools.

Common utility functions used across multiple tools, such as web content fetching.
"""

import httpx

from agents.resources import register_tool


@register_tool(
    group="web",
    description="Fetch a webpage and convert its HTML content to Markdown.",
)
def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch a webpage and convert its HTML content to Markdown.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds.

    Returns:
        The webpage content converted to Markdown, or an error message on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        return markdownify(response.text)
    except httpx.HTTPStatusError as e:
        return f"HTTP error fetching {url}: {e.response.status_code} {e.response.reason_phrase}"
    except Exception as e:
        return f"Error fetching content from {url}: {e}"
