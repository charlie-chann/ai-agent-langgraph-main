# tools/file_tool.py — Safe read/write within ./workspace/ sandbox
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

# Sandboxed directory — all file ops are restricted here
SANDBOX = Path(__file__).parent.parent / "workspace"
SANDBOX.mkdir(exist_ok=True)


def _safe_path(filename: str) -> Path:
    """Resolve and validate path stays within sandbox."""
    p = (SANDBOX / filename).resolve()
    if not str(p).startswith(str(SANDBOX.resolve())):
        raise ValueError(f"Path traversal attempt blocked: {filename!r}")
    return p


@tool
def file_read(filename: str) -> str:
    """Read a text file from the sandbox workspace folder.
    Input: filename (relative, e.g. 'notes.txt').
    Returns: file contents or error message.
    """
    try:
        path = _safe_path(filename)
        if not path.exists():
            return f"File not found: {filename}"
        content = path.read_text(encoding="utf-8")
        logger.info(f"[file_read] {path}")
        return content[:10_000]  # cap at 10k chars for context window
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def file_write(filename: str, content: str) -> str:
    """Write text to a file in the sandbox workspace folder.
    Input: filename (relative), content (text to write).
    Returns: success/error message.
    """
    try:
        path = _safe_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info(f"[file_write] {path} ({len(content)} chars)")
        return f"Written {len(content)} characters to {filename}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def file_list(subfolder: str = "") -> str:
    """List files in the sandbox workspace.
    Input: optional subfolder name (default: root of workspace).
    Returns: list of filenames.
    """
    try:
        base = _safe_path(subfolder) if subfolder else SANDBOX
        if not base.is_dir():
            return f"Not a directory: {subfolder}"
        files = [str(f.relative_to(SANDBOX)) for f in base.iterdir()]
        return "\n".join(files) if files else "(empty)"
    except Exception as e:
        return f"Error listing files: {e}"
