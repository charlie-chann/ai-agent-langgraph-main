# tools/file_tool.py — sandboxed file read/write for code workspace
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

from config import SANDBOX_DIR

SANDBOX = Path(SANDBOX_DIR)
SANDBOX.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".sh", ".txt", ".md", ".json", ".yaml", ".yml", ".toml"}


def _safe_path(filename: str) -> Path:
    p = (SANDBOX / filename).resolve()
    if not str(p).startswith(str(SANDBOX.resolve())):
        raise ValueError(f"Path traversal blocked: {filename!r}")
    if p.suffix not in ALLOWED_EXTENSIONS and p.suffix != "":
        raise ValueError(f"Extension not allowed: {p.suffix}")
    return p


@tool
def read_code_file(filename: str) -> str:
    """Read a source code file from the sandbox workspace.
    Input: filename relative to workspace (e.g. 'main.py', 'utils/helpers.py').
    Returns: file contents.
    """
    try:
        path = _safe_path(filename)
        if not path.exists():
            return f"File not found: {filename}"
        return path.read_text(encoding="utf-8")[:8000]
    except Exception as e:
        return f"Error: {e}"


@tool
def write_code_file(filename: str, content: str) -> str:
    """Write source code to a file in the sandbox workspace.
    Args:
        filename: relative file path (e.g. 'main.py')
        content: source code content
    Returns: success or error message.
    """
    try:
        path = _safe_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info(f"[write_code] {path} ({len(content)} chars)")
        return f"✅ Written {len(content)} chars to {filename}"
    except Exception as e:
        return f"Error: {e}"


@tool
def list_workspace_files(subfolder: str = "") -> str:
    """List files in the code sandbox workspace.
    Input: optional subfolder name.
    Returns: list of files.
    """
    try:
        base = _safe_path(subfolder) if subfolder else SANDBOX
        if not base.is_dir():
            return f"Not a directory: {subfolder or 'workspace'}"
        files = sorted(str(f.relative_to(SANDBOX)) for f in base.rglob("*") if f.is_file())
        return "\n".join(files) if files else "(workspace is empty)"
    except Exception as e:
        return f"Error: {e}"
