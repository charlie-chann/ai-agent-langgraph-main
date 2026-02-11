# tools/code_executor.py — Safe sandboxed code execution
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

from config import CODE_EXEC_TIMEOUT, SANDBOX_DIR, ALLOWED_LANGUAGES

SANDBOX = Path(SANDBOX_DIR)
SANDBOX.mkdir(exist_ok=True)

_BLOCKED_PATTERNS = [
    "import os", "import sys", "import subprocess",
    "__import__", "eval(", "exec(",
    "open(", "os.system", "os.popen",
    "shutil", "socket", "urllib", "requests",
    "rm -rf", "del /", "format c",
]


def _is_safe(code: str, language: str) -> tuple[bool, str]:
    """Basic static analysis to block obviously dangerous code."""
    code_lower = code.lower()
    if language == "python":
        for pattern in _BLOCKED_PATTERNS:
            if pattern in code_lower:
                return False, f"Blocked pattern detected: '{pattern}'"
    return True, "ok"


@tool
def execute_python(code: str) -> str:
    """Execute Python code in a safe sandbox and return stdout/stderr.
    Input: valid Python code string (no file I/O, no network, no subprocess).
    Returns: execution output or error message.
    Max execution time: 10 seconds.
    """
    code = code.strip()
    if not code:
        return "Error: empty code"

    safe, reason = _is_safe(code, "python")
    if not safe:
        return f"Security block: {reason}"

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", dir=SANDBOX, delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=CODE_EXEC_TIMEOUT,
            cwd=str(SANDBOX),
        )
        os.unlink(tmp_path)

        output = result.stdout[:2000]
        errors = result.stderr[:1000]
        if errors:
            return f"Output:\n{output}\n\nErrors:\n{errors}" if output else f"Error:\n{errors}"
        return output or "(no output)"

    except subprocess.TimeoutExpired:
        return f"Execution timeout ({CODE_EXEC_TIMEOUT}s exceeded)"
    except Exception as e:
        logger.error(f"[execute_python] {e}")
        return f"Execution error: {e}"


@tool
def lint_python(code: str) -> str:
    """Check Python code for syntax errors and basic style issues using ast.parse.
    Input: Python code string.
    Returns: 'OK' or list of issues found.
    """
    import ast
    code = code.strip()
    if not code:
        return "Error: empty code"
    try:
        tree = ast.parse(code)
        # Check for common issues
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"os", "sys", "subprocess", "socket"}:
                        issues.append(f"Line {node.lineno}: Import of '{alias.name}' flagged for review")
        if issues:
            return "Issues found:\n" + "\n".join(issues)
        return "✅ No syntax errors. Code looks clean."
    except SyntaxError as e:
        return f"❌ Syntax error at line {e.lineno}: {e.msg}"
