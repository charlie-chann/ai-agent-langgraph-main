"""热点追踪 Agent - 核心业务逻辑"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    ALERT_THRESHOLD, MAX_TRACKED_TOPICS
)
from tools.trend_detector import (
    detect_trend_signals, compute_composite_heat,
    classify_heat_level, compute_momentum, TrendReport, TrendSignal
)
from tools.opportunity_analyzer import analyze_content_opportunities, generate_content_calendar


def _sanitize_input(text: str) -> str:
    text = text.strip()
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:500]


def _load_tracked_topics() -> list[dict]:
    """加载 data/topics.json 中的追踪话题"""
    data_path = Path(__file__).parent.parent / "data" / "topics.json"
    if data_path.exists():
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, KeyError):
            pass
    return [
        {"name": "AI科技", "priority": "high"},
        {"name": "创业", "priority": "medium"},
    ]


def run_track_topic(topic: str, keywords: list[str] | None = None) -> dict:
    """
    追踪单个话题的热度趋势。
    
    Returns: {
        success, report, heat_level, heat_score, alert, opportunities, error
    }
    """
    topic = _sanitize_input(topic)
    if not topic:
        return {"success": False, "error": "话题不能为空", "report": None}

    try:
        signals = detect_trend_signals(topic, keywords)
        heat_score = compute_composite_heat(signals)
        heat_level = classify_heat_level(heat_score)
        avg_momentum = (
            round(sum(s.momentum for s in signals) / len(signals), 3)
            if signals else 0.0
        )
        alert = heat_score >= ALERT_THRESHOLD
        opportunities = analyze_content_opportunities(topic, heat_level, heat_score)
        calendar = generate_content_calendar(topic, heat_score)

        summary = (
            f"话题「{topic}」当前热度 {heat_score:.0%}，"
            f"状态为【{heat_level}】，"
            f"{'热度上升中 🔥' if avg_momentum > 0 else '热度趋稳或下降'}。"
        )

        report = TrendReport(
            topic=topic,
            heat_level=heat_level,
            heat_score=heat_score,
            momentum=avg_momentum,
            top_signals=signals[:5],
            alert=alert,
            summary=summary,
            content_opportunities=opportunities
        )

        return {
            "success": True,
            "report": report,
            "heat_level": heat_level,
            "heat_score": heat_score,
            "alert": alert,
            "opportunities": opportunities,
            "calendar": calendar,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e), "report": None}


def run_batch_track(topics: list[str] | None = None) -> list[dict]:
    """批量追踪多个话题"""
    if topics is None:
        loaded = _load_tracked_topics()
        topics = [t["name"] if isinstance(t, dict) else t for t in loaded]

    topics = [_sanitize_input(t) for t in topics if t.strip()][:MAX_TRACKED_TOPICS]
    return [run_track_topic(t) for t in topics]


def run_get_trending(top_n: int = 5) -> list[dict]:
    """获取当前最热话题排行"""
    topics_data = _load_tracked_topics()
    topic_names = [t["name"] if isinstance(t, dict) else t for t in topics_data]
    results = run_batch_track(topic_names)

    successful = [r for r in results if r.get("success")]
    sorted_results = sorted(successful, key=lambda r: r.get("heat_score", 0), reverse=True)
    return sorted_results[:top_n]


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与趋势追踪 Agent 的流式对话"""
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
            "你是一位专业的内容趋势分析师，擅长分析社交媒体热点、内容传播规律和创作机会。"
            "只基于已有数据做分析，不臆测未经证实的信息。"
        )),
        HumanMessage(content=user_input)
    ]
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
