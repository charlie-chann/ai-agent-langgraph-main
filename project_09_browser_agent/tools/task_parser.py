# tools/task_parser.py — 浏览器任务解析与安全校验
#
# 【职责】
#   parse_task()         → 把自然语言指令解析为结构化 BrowserTask
#   sanitize_instruction() → 清洗输入、拦截 Prompt Injection
#
# 【被谁调用】
#   agent.run_browser_task / stream_browser_task 入口先调 sanitize
#   node_synthesize_report 调 parse_task 获取任务类型
"""
解析用户描述的浏览器自动化任务，拆解为可执行的操作步骤。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BrowserTask:
    """结构化的浏览器任务描述，供 synthesize 节点生成报告时参考。"""
    raw_instruction: str                              # 用户原始指令
    task_type: str = "research"                       # research | form_fill | monitor | extract
    target_urls: list[str] = field(default_factory=list)   # 从指令中提取的 URL
    keywords: list[str] = field(default_factory=list)      # 提取的关键词
    output_format: str = "text"                       # text | json | markdown
    max_pages: int = 5                                # 最多访问页面数（预留）


_URL_PATTERN = re.compile(r'https?://[^\s\'"<>]+')
# 关键词 → 任务类型映射表
_TASK_TYPE_MAP = {
    ("搜索", "查找", "研究", "了解", "调研", "search", "research", "find"): "research",
    ("填写", "提交", "登录", "注册", "form", "fill", "submit", "login"): "form_fill",
    ("监控", "监测", "定时", "monitor", "watch", "track"): "monitor",
    ("提取", "爬取", "抓取", "收集", "extract", "scrape", "crawl"): "extract",
}


def parse_task(instruction: str) -> BrowserTask:
    """
    将自然语言指令解析为 BrowserTask 结构体。

    步骤：提取 URL → 判断任务类型 → 提取关键词
    """
    task = BrowserTask(raw_instruction=instruction)

    # 从指令中正则提取所有 http(s) URL
    urls = _URL_PATTERN.findall(instruction)
    task.target_urls = urls

    # 根据关键词判断任务类型（research / extract 等）
    inst_lower = instruction.lower()
    for keywords, task_type in _TASK_TYPE_MAP.items():
        if any(kw in inst_lower for kw in keywords):
            task.task_type = task_type
            break

    # 提取有效词（>2字符，过滤停用词），最多 10 个
    stopwords = {"的", "了", "是", "在", "我", "你", "他", "她", "它", "们", "和", "或", "a", "an", "the", "is", "are"}
    words = re.findall(r'[\w\u4e00-\u9fff]{2,}', instruction)
    task.keywords = [w for w in words if w.lower() not in stopwords][:10]

    return task


def sanitize_instruction(instruction: str) -> str:
    """
    清理并校验用户输入，防止 Prompt Injection 攻击。

    Raises:
        ValueError: 输入为空或包含注入模式时抛出
    """
    if not instruction or not instruction.strip():
        raise ValueError("指令不能为空")
    # 拦截常见 Prompt Injection 模式
    injection_patterns = [
        r'ignore\s+(previous|above|all)\s+instruction',
        r'system\s*:\s*',
        r'<\|.*?\|>',
        r'\[INST\]|\[/INST\]',
    ]
    for pattern in injection_patterns:
        if re.search(pattern, instruction, re.IGNORECASE):
            raise ValueError("输入包含不允许的内容，请重新描述任务")
    return instruction.strip()[:2000]  # 限制最大 2000 字符
