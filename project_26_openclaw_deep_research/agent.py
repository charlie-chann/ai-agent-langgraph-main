"""深度调研 Agent - 核心业务逻辑"""

import re
from pathlib import Path
from datetime import datetime
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    DEFAULT_DEPTH, REPORTS_DIR, MAX_REPORT_LENGTH
)
from tools.research_engine import (
    generate_sub_queries, search_sources, cross_validate_findings,
    QueryResult, ResearchSource
)
from tools.report_generator import build_report, generate_report_markdown, ResearchReport


def _sanitize_input(text: str) -> str:
    text = text.strip()
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:500]


def _execute_research(topic: str, depth: str) -> list[QueryResult]:
    """执行多轮搜索，返回 QueryResult 列表"""
    queries = generate_sub_queries(topic, depth)
    results: list[QueryResult] = []
    for q in queries:
        sources = search_sources(q)
        confidence = (
            sum(s.credibility_score for s in sources) / len(sources)
            if sources else 0.0
        )
        results.append(QueryResult(
            query=q,
            sources=sources,
            summary=f"针对「{q}」共检索到 {len(sources)} 个来源。",
            confidence=round(confidence, 2)
        ))
    return results


def run_research(topic: str, depth: str = DEFAULT_DEPTH) -> dict:
    """
    执行完整深度调研流程。
    
    Returns: {
        success, report, content, total_sources, avg_credibility, error
    }
    """
    topic = _sanitize_input(topic)
    if not topic:
        return {"success": False, "error": "话题不能为空", "report": None, "content": ""}

    if depth not in ["quick", "standard", "deep"]:
        depth = DEFAULT_DEPTH

    try:
        query_results = _execute_research(topic, depth)
        validation = cross_validate_findings(query_results)
        report = build_report(topic, depth, query_results, validation)
        content = generate_report_markdown(report)
        if len(content) > MAX_REPORT_LENGTH:
            content = content[:MAX_REPORT_LENGTH] + "\n\n…（内容已截断）"

        return {
            "success": True,
            "report": report,
            "content": content,
            "total_sources": report.total_sources,
            "avg_credibility": report.avg_credibility,
            "error": None
        }
    except Exception as e:
        return {"success": False, "report": None, "content": "", "error": str(e)}


def run_validate_topic(topic: str) -> dict:
    """快速验证话题：返回是否有足够数据支持调研"""
    topic = _sanitize_input(topic)
    sources = search_sources(topic, max_results=3)
    return {
        "topic": topic,
        "source_count": len(sources),
        "avg_credibility": round(
            sum(s.credibility_score for s in sources) / len(sources), 2
        ) if sources else 0.0,
        "researchable": len(sources) >= 2
    }


def run_save_report(report: ResearchReport) -> dict:
    """保存报告到 reports/ 目录"""
    reports_dir = Path(__file__).parent / REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = reports_dir / filename
    content = generate_report_markdown(report)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return {"success": True, "path": str(filepath)}


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与调研 Agent 的流式对话"""
    from langchain_community.chat_models import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage

    user_input = _sanitize_input(user_input)
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE
    )
    messages = [
        SystemMessage(content=(
            "你是一位专业的研究分析师，擅长深度调研、信息验证和报告撰写。"
            "请基于事实和可靠数据回答问题，若不确定请明确说明。"
        )),
        HumanMessage(content=user_input)
    ]
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
