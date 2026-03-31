"""Tests for the Modal sandbox tools.

Covers sandbox_exec, sandbox_upload, sandbox_download, and sandbox lifecycle
management. These tests do NOT require a real Modal setup — they mock the
Modal SDK to test the tool logic in isolation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock the Modal SDK before importing the tools module
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_modal():
    """Automatically mock the Modal SDK for all tests."""
    mock_sb = MagicMock()
    mock_proc = MagicMock()
    mock_proc.stdout.read.return_value = "hello world"
    mock_proc.stderr.read.return_value = ""
    mock_proc.exit_code = 0
    mock_sb.exec_process.return_value = mock_proc

    mock_app = MagicMock()
    mock_app.lookup.return_value = mock_app

    mock_modal = MagicMock()
    mock_modal.Sandbox.create.return_value = mock_sb
    mock_modal.App.lookup.return_value = mock_app

    with (
        patch.dict("sys.modules", {"modal": mock_modal}),
        patch("tools.sandbox.modal", mock_modal),
        patch("tools.sandbox._MODAL_AVAILABLE", True),
    ):
        # Re-import to pick up the mocked module
        import importlib
        import tools.sandbox as sb_mod
        importlib.reload(sb_mod)

        # Reset module-level state
        sb_mod._sandbox = None
        sb_mod._app = None

        yield {
            "modal": mock_modal,
            "sandbox": mock_sb,
            "process": mock_proc,
            "app": mock_app,
            "module": sb_mod,
        }


# ---------------------------------------------------------------------------
# sandbox_exec tests
# ---------------------------------------------------------------------------

class TestSandboxExec:
    """Tests for the sandbox_exec tool."""

    def test_basic_execution(self, _mock_modal):
        """Test basic command execution returns stdout and exit code."""
        from tools.sandbox import sandbox_exec

        result = sandbox_exec.invoke({"command": "echo hello"})
        assert "hello world" in result
        assert "Exit code: 0" in result

    def test_execution_timeout_passed(self, _mock_modal):
        """Test that timeout parameter is forwarded to exec_process."""
        from tools.sandbox import sandbox_exec

        sandbox_exec.invoke({"command": "sleep 1", "timeout": 300})
        _mock_modal["sandbox"].exec_process.assert_called()
        call_kwargs = _mock_modal["sandbox"].exec_process.call_args
        assert call_kwargs.kwargs.get("timeout") == 300

    def test_execution_failure(self, _mock_modal):
        """Test that non-zero exit code is reported."""
        _mock_modal["process"].exit_code = 1
        _mock_modal["process"].stderr.read.return_value = "command not found"

        from tools.sandbox import sandbox_exec

        result = sandbox_exec.invoke({"command": "nonexistent_cmd"})
        assert "Exit code: 1" in result
        assert "command not found" in result

    def test_output_truncation(self, _mock_modal):
        """Test that long output is truncated."""
        long_output = "x" * 20000
        _mock_modal["process"].stdout.read.return_value = long_output

        from tools.sandbox import sandbox_exec

        result = sandbox_exec.invoke({"command": "cat huge_file"})
        assert "truncated" in result
        assert len(result) < 30000  # Should be much shorter than 20000 raw chars


# ---------------------------------------------------------------------------
# sandbox_upload tests
# ---------------------------------------------------------------------------

class TestSandboxUpload:
    """Tests for the sandbox_upload tool."""

    def test_upload_success(self, _mock_modal):
        """Test successful file upload returns confirmation."""
        from tools.sandbox import sandbox_upload

        result = sandbox_upload.invoke({
            "filepath": "/home/user/test.py",
            "content": "print('hello')",
        })
        assert "uploaded to sandbox" in result
        assert "test.py" in result
        assert "14 bytes" in result  # len("print('hello')")

    def test_upload_creates_directory(self, _mock_modal):
        """Test that upload creates parent directories."""
        from tools.sandbox import sandbox_upload

        sandbox_upload.invoke({
            "filepath": "/deep/nested/dir/file.py",
            "content": "# code",
        })

        calls = _mock_modal["sandbox"].exec_process.call_args_list
        mkdir_call = str(calls[0])
        assert "mkdir -p" in mkdir_call


# ---------------------------------------------------------------------------
# sandbox_download tests
# ---------------------------------------------------------------------------

class TestSandboxDownload:
    """Tests for the sandbox_download tool."""

    def test_download_success(self, _mock_modal):
        """Test successful file download returns content."""
        _mock_modal["process"].stdout.read.return_value = "file content here"

        from tools.sandbox import sandbox_download

        result = sandbox_download.invoke({"filepath": "/home/user/output.txt"})
        assert result == "file content here"

    def test_download_file_not_found(self, _mock_modal):
        """Test download of non-existent file returns error."""
        _mock_modal["process"].exit_code = 1
        _mock_modal["process"].stderr.read.return_value = "No such file"

        from tools.sandbox import sandbox_download

        result = sandbox_download.invoke({"filepath": "/nonexistent"})
        assert "Error" in result or "not found" in result

    def test_download_truncation(self, _mock_modal):
        """Test that large file downloads are truncated."""
        long_content = "y" * 20000
        _mock_modal["process"].stdout.read.return_value = long_content

        from tools.sandbox import sandbox_download

        result = sandbox_download.invoke({"filepath": "/large_file"})
        assert "too large" in result


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------

class TestSandboxLifecycle:
    """Tests for sandbox instance lifecycle management."""

    def test_sandbox_reuse(self, _mock_modal):
        """Test that sandbox instance is reused across calls."""
        from tools.sandbox import sandbox_exec, _get_sandbox

        sandbox_exec.invoke({"command": "echo a"})
        sb1 = _get_sandbox()

        sandbox_exec.invoke({"command": "echo b"})
        sb2 = _get_sandbox()

        assert sb1 is sb2  # Same instance
        _mock_modal["modal"].Sandbox.create.assert_called_once()

    def test_cleanup(self, _mock_modal):
        """Test that cleanup terminates the sandbox."""
        from tools.sandbox import _cleanup_sandbox, _get_sandbox

        _get_sandbox()  # Create the sandbox
        _cleanup_sandbox()

        _mock_modal["sandbox"].terminate.assert_called_once()

    def test_no_modal_returns_error(self):
        """Test graceful degradation when Modal is not installed."""
        with patch("tools.sandbox._MODAL_AVAILABLE", False):
            import importlib
            import tools.sandbox as sb_mod
            importlib.reload(sb_mod)

            from tools.sandbox import sandbox_exec
            result = sandbox_exec.invoke({"command": "echo test"})
            assert "Error" in result
            assert "not available" in result


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Tests for tool registration with ResourceRegistry."""

    def test_tools_registered(self, _mock_modal):
        """Test that sandbox tools are registered in ResourceRegistry."""
        from agents.resources import resource_registry
        from tools.sandbox import sandbox_exec, sandbox_upload, sandbox_download

        assert resource_registry.get_tool("sandbox_exec") is not None
        assert resource_registry.get_tool("sandbox_upload") is not None
        assert resource_registry.get_tool("sandbox_download") is not None

    def test_tools_in_code_group(self, _mock_modal):
        """Test that sandbox tools belong to the 'code' group."""
        from agents.resources import resource_registry

        code_tools = resource_registry.tool_names_by_group("code")
        assert "sandbox_exec" in code_tools
        assert "sandbox_upload" in code_tools
        assert "sandbox_download" in code_tools
