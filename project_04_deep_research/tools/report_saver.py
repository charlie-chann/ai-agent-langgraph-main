# tools/report_saver.py — save final report to markdown/txt files
from pathlib import Path
import time
from loguru import logger
from config import REPORT_OUTPUT_DIR


def save_report(topic: str, content: str) -> Path:
    """Save report to disk and return path."""
    out_dir = Path(REPORT_OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic[:50]).strip()
    ts = int(time.time())
    filename = f"report_{safe_name}_{ts}.md"
    path = out_dir / filename

    path.write_text(content, encoding="utf-8")
    logger.info(f"Report saved: {path}")
    return path
