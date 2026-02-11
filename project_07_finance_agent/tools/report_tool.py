# tools/report_tool.py — Save financial research reports to disk
from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import datetime, timezone

from langchain_core.tools import tool
from loguru import logger

from config import REPORTS_DIR

_REPORTS = Path(REPORTS_DIR)
_REPORTS.mkdir(exist_ok=True)


@tool
def save_report(title: str, content: str) -> str:
    """Save a financial research report as a Markdown file.
    Args:
        title: report title (used as filename, e.g. 'AAPL_analysis')
        content: full Markdown report content
    Returns: path to saved file.
    """
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:80]
    ts = int(time.time())
    filename = f"{safe_title}_{ts}.md"
    path = _REPORTS / filename
    path.write_text(content, encoding="utf-8")
    logger.info(f"[report] saved {path}")
    return f"✅ Report saved to {path}"


@tool
def list_reports() -> str:
    """List all saved financial research reports.
    Returns: JSON list of saved reports with filenames and creation times.
    """
    files = sorted(_REPORTS.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    items = [
        {
            "filename": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "created": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for f in files[:20]
    ]
    return json.dumps(items, ensure_ascii=False, indent=2) if items else "No reports saved yet."


@tool
def read_report(filename: str) -> str:
    """Read a previously saved financial report.
    Input: report filename (from list_reports).
    Returns: report contents.
    """
    safe = Path(filename).name  # strip any path component
    path = _REPORTS / safe
    if not path.exists():
        return f"Report not found: {filename}"
    return path.read_text(encoding="utf-8")[:10000]
