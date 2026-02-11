"""
tools/file_tool.py — 沙箱文件读写工具

【职责】
1. file_read / file_write / file_list 三个 @tool，限制在 ./workspace/ 目录内操作
2. 通过 _safe_path 防止路径穿越攻击（如 ../../etc/passwd）

【设计原因】
1. Agent 需要持久化笔记、读写中间结果，但不能访问整个文件系统
2. 沙箱目录与项目代码隔离，误删也不会破坏源码
3. 读文件限制 10k 字符，避免撑爆 LLM 上下文窗口
"""
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

# 沙箱根目录：所有文件操作只能在此目录及其子目录内进行
SANDBOX = Path(__file__).parent.parent / "workspace"
SANDBOX.mkdir(exist_ok=True)


def _safe_path(filename: str) -> Path:
    """
    将相对路径解析为绝对路径，并校验仍在沙箱内。

    参数:
        filename: 相对于 workspace 的文件路径

    返回:
        解析后的 Path 对象

    异常:
        ValueError: 路径试图逃出沙箱（路径穿越攻击）
    """
    p = (SANDBOX / filename).resolve()
    # resolve() 后检查前缀，阻止 ../ 逃逸
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
        # 截断过长内容，保护上下文窗口
        return content[:10_000]
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
        # 若子目录不存在则自动创建（如 notes/sub/file.txt）
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
        # subfolder 为空则列出 workspace 根目录
        base = _safe_path(subfolder) if subfolder else SANDBOX
        if not base.is_dir():
            return f"Not a directory: {subfolder}"
        # 返回相对路径列表，便于 Agent 后续 file_read
        files = [str(f.relative_to(SANDBOX)) for f in base.iterdir()]
        return "\n".join(files) if files else "(empty)"
    except Exception as e:
        return f"Error listing files: {e}"
