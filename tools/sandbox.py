"""Modal sandbox execution tools.

Provides isolated code execution capabilities via Modal sandboxes.
All tools are registered with the global ResourceRegistry under the ``code`` group.

Requires the ``modal`` package. Install with::

    pip install modal

Modal also requires authentication. Set up with::

    modal token new
    # or set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET env vars

When Modal is not available, all tools return descriptive error messages
rather than raising exceptions, ensuring graceful degradation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency check
# ---------------------------------------------------------------------------

try:
    import modal

    _MODAL_AVAILABLE = True
except ImportError:
    _MODAL_AVAILABLE = False
    logger.warning(
        "modal package not installed. "
        "Sandbox tools will be unavailable. Install with: pip install modal"
    )

# ---------------------------------------------------------------------------
# Sandbox instance management (module-level, lazily created)
# ---------------------------------------------------------------------------

_sandbox: modal.Sandbox | None = None
_app: modal.App | None = None


def _ensure_modal_app() -> modal.App:
    """Get or create the Modal App used for sandbox creation."""
    global _app
    if _app is None:
        _app = modal.App.lookup(
            os.getenv("MODAL_APP_NAME", "agents-sandbox"),
            environment_name=os.getenv("MODAL_ENVIRONMENT", None),
        )
    return _app


def _get_sandbox() -> modal.Sandbox | None:
    """Get or create the shared Modal Sandbox instance.

    Returns ``None`` if Modal is not available. The sandbox is lazily
    created on first access and reused across subsequent calls within
    the same process.
    """
    global _sandbox
    if not _MODAL_AVAILABLE:
        return None
    if _sandbox is None:
        try:
            app = _ensure_modal_app()
            _sandbox = modal.Sandbox.create(app=app)
            logger.info("Modal sandbox created successfully.")
        except Exception as e:
            logger.error("Failed to create Modal sandbox: %s", e)
            return None
    return _sandbox


def _cleanup_sandbox() -> None:
    """Terminate the shared Modal Sandbox instance.

    Should be called during application shutdown to free resources.
    """
    global _sandbox, _app
    if _sandbox is not None:
        try:
            _sandbox.terminate()
            logger.info("Modal sandbox terminated.")
        except Exception as e:
            logger.warning("Error terminating Modal sandbox: %s", e)
        _sandbox = None
    _app = None


# ---------------------------------------------------------------------------
# Output truncation helper
# ---------------------------------------------------------------------------

_MAX_OUTPUT_LENGTH = 10000


def _truncate(text: str, label: str = "output") -> str:
    """Truncate text if it exceeds the maximum length."""
    if len(text) > _MAX_OUTPUT_LENGTH:
        return (
            f"[{label} truncated: showing first {_MAX_OUTPUT_LENGTH} of "
            f"{len(text)} characters]\n"
            f"{text[:_MAX_OUTPUT_LENGTH]}"
        )
    return text


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

from agents.resources import register_tool


@register_tool(
    group="code",
    description=(
        "Execute a shell command in an isolated Modal sandbox environment. "
        "Supports running Python scripts, installing packages, and any other "
        "shell operations. Returns stdout, stderr, and exit code."
    ),
)
def sandbox_exec(command: str, timeout: int = 120) -> str:
    """Execute a shell command in an isolated Modal sandbox.

    Use this tool to run code, install packages, execute scripts, and perform
    any computation in a secure, isolated environment. Each call executes
    the command and returns the result.

    Tips:
    - Use ``pip install`` to install dependencies before running code.
    - Write multi-line scripts using heredoc or ``python -c``.
    - Chain commands with ``&&`` or ``;``.
    - The sandbox persists between calls, so installed packages remain.

    Args:
        command: The shell command to execute in the sandbox.
        timeout: Maximum execution time in seconds (default: 120).

    Returns:
        Formatted output including stdout, stderr, and exit code.
    """
    if not _MODAL_AVAILABLE:
        return (
            "Error: Modal is not available. The 'modal' package must be "
            "installed and authenticated. Install with: pip install modal, "
            "then run: modal token new"
        )

    sb = _get_sandbox()
    if sb is None:
        return "Error: Could not create or access the Modal sandbox. Check Modal authentication."

    try:
        proc = sb.exec_process(
            command,
            timeout=timeout,
        )

        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
        exit_code = proc.exit_code if hasattr(proc, "exit_code") else "unknown"

        parts: list[str] = []

        if stdout:
            parts.append(f"## stdout\n{_truncate(stdout, 'stdout')}")

        if stderr:
            parts.append(f"## stderr\n{_truncate(stderr, 'stderr')}")

        parts.append(f"**Exit code:** {exit_code}")

        if exit_code == 0:
            parts.insert(0, "✅ Command completed successfully.")
        else:
            parts.insert(0, f"❌ Command failed with exit code {exit_code}.")

        return "\n\n".join(parts)

    except Exception as e:
        return f"Error executing command in Modal sandbox: {e}"


@register_tool(
    group="code",
    description=(
        "Upload a file to the Modal sandbox environment. "
        "Useful for providing input files, scripts, or data to the sandbox."
    ),
)
def sandbox_upload(filepath: str, content: str) -> str:
    """Upload a file to the Modal sandbox.

    Creates or overwrites a file at the specified path inside the sandbox.

    Args:
        filepath: Target path inside the sandbox (e.g., ``/home/user/main.py``).
        content: The file content as a string.

    Returns:
        Confirmation message or error description.
    """
    if not _MODAL_AVAILABLE:
        return (
            "Error: Modal is not available. Install with: pip install modal"
        )

    sb = _get_sandbox()
    if sb is None:
        return "Error: Could not access Modal sandbox."

    try:
        # Modal sandbox provides a working directory; write relative to it
        sb.exec_process(f"mkdir -p {os.path.dirname(filepath) or '.'}")
        # Use a heredoc approach to write content to file
        # Escape any single quotes in content
        safe_content = content.replace("'", "'\\''")
        sb.exec_process(f"cat > {filepath} << 'SANDBOX_UPLOAD_EOF'\n{content}\nSANDBOX_UPLOAD_EOF")

        return f"✅ File uploaded to sandbox: {filepath} ({len(content)} bytes)"
    except Exception as e:
        return f"Error uploading file to sandbox: {e}"


@register_tool(
    group="code",
    description=(
        "Download a file from the Modal sandbox environment. "
        "Returns the file content as a string."
    ),
)
def sandbox_download(filepath: str) -> str:
    """Download a file from the Modal sandbox.

    Reads the content of a file inside the sandbox and returns it.

    Args:
        filepath: Path to the file inside the sandbox.

    Returns:
        The file content as a string, or an error description.
    """
    if not _MODAL_AVAILABLE:
        return (
            "Error: Modal is not available. Install with: pip install modal"
        )

    sb = _get_sandbox()
    if sb is None:
        return "Error: Could not access Modal sandbox."

    try:
        # Check if file exists and get size
        check = sb.exec_process(f"wc -c {filepath}")
        if hasattr(check, "exit_code") and check.exit_code != 0:
            stderr = check.stderr.read() if check.stderr else "Unknown error"
            return f"Error: File not found or not readable: {filepath}\n{stderr}"

        # Read file content
        proc = sb.exec_process(f"cat {filepath}")
        content = proc.stdout.read() if proc.stdout else ""

        if len(content) > _MAX_OUTPUT_LENGTH:
            return (
                f"⚠️ File too large to display fully ({len(content)} bytes). "
                f"Showing first {_MAX_OUTPUT_LENGTH} characters.\n\n"
                f"{content[:_MAX_OUTPUT_LENGTH]}"
            )

        return content
    except Exception as e:
        return f"Error downloading file from sandbox: {e}"


__all__ = [
    "sandbox_exec",
    "sandbox_upload",
    "sandbox_download",
    "_cleanup_sandbox",
]
