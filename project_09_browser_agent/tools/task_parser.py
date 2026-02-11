# tools/task_parser.py — Parse and validate browser automation tasks
"""
解析用户描述的浏览器自动化任务，拆解为可执行的操作步骤。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrowserTask:
    """结构化的浏览器任务描述"""
    raw_instruction: str
    task_type: str = "research"   # research | form_fill | monitor | extract
    target_urls: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    output_format: str = "text"   # text | json | markdown
    max_pages: int = 5


_URL_PATTERN = re.compile(r'https?://[^\s\'"<>]+')
_TASK_TYPE_MAP = {
    ("搜索", "查找", "研究", "了解", "调研", "search", "research", "find"): "research",
    ("填写", "提交", "登录", "注册", "form", "fill", "submit", "login"): "form_fill",
    ("监控", "监测", "定时", "monitor", "watch", "track"): "monitor",
    ("提取", "爬取", "抓取", "收集", "extract", "scrape", "crawl"): "extract",
}


def parse_task(instruction: str) -> BrowserTask:
    """将自然语言指令解析为 BrowserTask。"""
    task = BrowserTask(raw_instruction=instruction)

    # Extract URLs from instruction
    urls = _URL_PATTERN.findall(instruction)
    task.target_urls = urls

    # Determine task type
    inst_lower = instruction.lower()
    for keywords, task_type in _TASK_TYPE_MAP.items():
        if any(kw in inst_lower for kw in keywords):
            task.task_type = task_type
            break

    # Extract keywords (simple: words > 2 chars, excluding stopwords)
    stopwords = {"的", "了", "是", "在", "我", "你", "他", "她", "它", "们", "和", "或", "a", "an", "the", "is", "are"}
    words = re.findall(r'[\w\u4e00-\u9fff]{2,}', instruction)
    task.keywords = [w for w in words if w.lower() not in stopwords][:10]

    return task


def sanitize_instruction(instruction: str) -> str:
    """清理用户输入，防止 prompt injection。"""
    if not instruction or not instruction.strip():
        raise ValueError("指令不能为空")
    # Remove potential prompt injection patterns
    injection_patterns = [
        r'ignore\s+(previous|above|all)\s+instruction',
        r'system\s*:\s*',
        r'<\|.*?\|>',
        r'\[INST\]|\[/INST\]',
    ]
    for pattern in injection_patterns:
        if re.search(pattern, instruction, re.IGNORECASE):
            raise ValueError("输入包含不允许的内容，请重新描述任务")
    return instruction.strip()[:2000]
