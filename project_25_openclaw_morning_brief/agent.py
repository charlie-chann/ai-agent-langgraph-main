"""早报 Agent - 核心业务逻辑"""

import re
import json
from datetime import datetime
from pathlib import Path
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    DEFAULT_RSS_SOURCES, MAX_BRIEF_LENGTH, REPORTS_DIR
)
from tools.rss_collector import collect_from_sources, RSSArticle
from tools.brief_generator import create_morning_brief, format_brief_for_display, MorningBrief


def _load_rss_sources() -> list[dict]:
    """从 data/rss-sources.json 加载 RSS 源，回退到默认配置"""
    data_path = Path(__file__).parent.parent / "data" / "rss-sources.json"
    if data_path.exists():
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sources = data.get("sources", [])
            if sources:
                return sources
        except (json.JSONDecodeError, KeyError):
            pass
    return DEFAULT_RSS_SOURCES


def _sanitize_input(text: str) -> str:
    """清洗用户输入，防止 prompt injection"""
    text = text.strip()
    # 移除可能的 prompt injection 模式
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:500]


def run_generate_brief(
    sources: list[dict] | None = None,
    date: str | None = None,
    output_format: str = "markdown"
) -> dict:
    """
    生成今日早报（同步）。
    
    Returns:
        {
            "success": bool,
            "brief": MorningBrief | None,
            "content": str,
            "article_count": int,
            "error": str | None
        }
    """
    sources = sources or _load_rss_sources()
    try:
        articles = collect_from_sources(sources)
        if not articles:
            return {
                "success": False,
                "brief": None,
                "content": "暂无可用资讯",
                "article_count": 0,
                "error": "No articles fetched"
            }
        brief = create_morning_brief(articles, date=date, output_format=output_format)
        content = format_brief_for_display(brief)
        # 截断到最大长度
        if len(content) > MAX_BRIEF_LENGTH:
            content = content[:MAX_BRIEF_LENGTH] + "\n\n…（内容已截断）"

        return {
            "success": True,
            "brief": brief,
            "content": content,
            "article_count": brief.headline_count,
            "error": None
        }
    except Exception as e:
        return {
            "success": False,
            "brief": None,
            "content": "",
            "article_count": 0,
            "error": str(e)
        }


def run_list_sources() -> list[dict]:
    """列出当前已配置的所有 RSS 源"""
    return _load_rss_sources()


def run_add_source(name: str, url: str, tags: list[str], category: str = "其他") -> dict:
    """添加新 RSS 源（写入本地配置）"""
    name = _sanitize_input(name)
    url = _sanitize_input(url)
    # 基本 URL 验证
    if not url.startswith("http"):
        return {"success": False, "error": "无效 URL"}

    sources = _load_rss_sources()
    # 检查重复
    for s in sources:
        if s["url"] == url:
            return {"success": False, "error": "该 URL 已存在"}

    sources.append({
        "name": name,
        "url": url,
        "tags": tags,
        "category": category,
        "enabled": True
    })

    data_path = Path(__file__).parent / "data" / "rss-sources-local.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"sources": sources}, f, ensure_ascii=False, indent=2)

    return {"success": True, "source_count": len(sources)}


def run_save_brief(brief: MorningBrief) -> dict:
    """将早报保存到 reports/ 目录"""
    reports_dir = Path(__file__).parent / REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"brief_{datetime.now().strftime('%Y%m%d')}.md"
    filepath = reports_dir / filename
    content = format_brief_for_display(brief)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {"success": True, "path": str(filepath)}


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与早报 Agent 的流式对话"""
    from langchain_community.chat_models import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage

    user_input = _sanitize_input(user_input)
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE
    )

    system_prompt = (
        "你是一位专业的新闻助手，负责帮助用户理解今日早报内容。"
        "你能够解释新闻背景、分析趋势、回答关于早报的各类问题。"
        "保持客观、专业，不要传播未经验证的信息。"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input)
    ]

    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
