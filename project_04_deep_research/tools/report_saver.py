"""
tools/report_saver.py — 研究报告持久化工具

【职责】
将 Agent 生成的最终报告写入本地 Markdown 文件，返回保存路径供 API/UI 展示。

【设计原因】
文件 I/O 与 Agent 核心逻辑分离，便于统一配置输出目录、
文件名规则，以及后续扩展 PDF/HTML 导出。
"""
from pathlib import Path
import time
from loguru import logger
from config import REPORT_OUTPUT_DIR


def save_report(topic: str, content: str) -> Path:
    """
    将研究报告保存为 Markdown 文件。

    Args:
        topic: 研究主题，用于生成文件名前缀
        content: 报告正文（Markdown 格式）

    Returns:
        已写入文件的 Path 对象
    """
    out_dir = Path(REPORT_OUTPUT_DIR)
    # 递归创建输出目录，exist_ok 避免并发或重复调用时报错
    out_dir.mkdir(parents=True, exist_ok=True)

    # 清洗文件名：仅保留字母数字及空格、下划线、连字符，防止路径注入
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic[:50]).strip()
    ts = int(time.time())  # 时间戳保证同名主题多次研究不覆盖
    filename = f"report_{safe_name}_{ts}.md"
    path = out_dir / filename

    path.write_text(content, encoding="utf-8")
    logger.info(f"Report saved: {path}")
    return path
