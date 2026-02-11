"""tests/test_agent.py — Unit tests for project_06_code_agent"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
import pytest


def _load(module_name: str, rel_path: str):
    """Load a project module by file path to avoid global 'agent' package clash."""
    path = Path(__file__).parent.parent / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── code_executor tests ────────────────────────────────────────────────────
class TestCodeExecutor:
    """Tests for sandbox code execution safety and correctness."""

    def setup_method(self):
        self.mod = _load("code_executor", "tools/code_executor.py")

    def test_safe_arithmetic(self):
        result = self.mod.execute_python.invoke("print(2 + 2)")
        assert "4" in result

    def test_safe_string_ops(self):
        result = self.mod.execute_python.invoke("s = 'hello'; print(s.upper())")
        assert "HELLO" in result

    def test_blocks_os_import(self):
        result = self.mod.execute_python.invoke("import os\nprint(os.getcwd())")
        assert "Security block" in result or "Blocked" in result

    def test_blocks_subprocess_import(self):
        result = self.mod.execute_python.invoke("import subprocess\nsubprocess.run(['ls'])")
        assert "Security block" in result or "Blocked" in result

    def test_blocks_sys_import(self):
        result = self.mod.execute_python.invoke("import sys\nprint(sys.path)")
        assert "Security block" in result or "Blocked" in result

    def test_blocks_eval(self):
        result = self.mod.execute_python.invoke("eval('1+1')")
        assert "Security block" in result or "Blocked" in result

    def test_empty_code_returns_error(self):
        result = self.mod.execute_python.invoke("")
        assert "Error" in result or "error" in result

    def test_syntax_error_captured(self):
        result = self.mod.execute_python.invoke("def foo(:\n    pass")
        # Should capture the syntax error, not crash
        assert result is not None
        assert len(result) > 0


# ── lint_python tests ──────────────────────────────────────────────────────
class TestLintPython:
    def setup_method(self):
        self.mod = _load("code_executor", "tools/code_executor.py")

    def test_clean_code_passes(self):
        result = self.mod.lint_python.invoke("def add(a, b):\n    return a + b")
        assert "✅" in result or "No syntax" in result

    def test_syntax_error_detected(self):
        result = self.mod.lint_python.invoke("def foo(:)\n    pass")
        assert "Syntax error" in result or "syntax" in result.lower()

    def test_flagged_import(self):
        result = self.mod.lint_python.invoke("import os\nprint('hi')")
        assert "flagged" in result.lower() or "Issues" in result

    def test_empty_code(self):
        result = self.mod.lint_python.invoke("")
        assert "Error" in result or "error" in result


# ── file_tool tests ────────────────────────────────────────────────────────
class TestFileTool:
    def setup_method(self):
        self.mod = _load("file_tool", "tools/file_tool.py")

    def test_write_and_read(self, tmp_path, monkeypatch):
        # Redirect sandbox to tmp
        monkeypatch.setattr(self.mod, "SANDBOX", tmp_path)
        write_result = self.mod.write_code_file.invoke({"filename": "test.py", "content": "x = 1"})
        assert "✅" in write_result or "Written" in write_result
        read_result = self.mod.read_code_file.invoke("test.py")
        assert "x = 1" in read_result

    def test_path_traversal_blocked(self):
        result = self.mod.read_code_file.invoke("../../etc/passwd")
        assert "blocked" in result.lower() or "Error" in result

    def test_list_empty_workspace(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.mod, "SANDBOX", tmp_path)
        result = self.mod.list_workspace_files.invoke("")
        assert "empty" in result or result == "(workspace is empty)"
