"""内容机会分析工具 - 基于趋势推荐创作方向"""

import re
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CONTENT_OPPORTUNITY_PLATFORMS


def _sanitize(text: str) -> str:
    return re.sub(r"[<>\"'\\]", "", text).strip()[:200]


def analyze_content_opportunities(
    topic: str,
    heat_level: str,
    heat_score: float,
    platforms: list[str] | None = None
) -> list[str]:
    """
    基于话题热度分析各平台内容创作机会。
    
    Returns:
        list of opportunity descriptions
    """
    topic = _sanitize(topic)
    platforms = platforms or CONTENT_OPPORTUNITY_PLATFORMS
    opportunities = []

    if heat_level in ("hot", "trending"):
        opportunities.append(f"🔥 [{topic}] 正处于爆发期，建议立即发布内容抢占流量窗口")

    platform_suggestions = {
        "微博": f"微博话题 #{topic}# 参与互动，发布简短热评（140字以内）",
        "小红书": f"小红书发布 {topic} 相关种草笔记，附高质量图片",
        "知乎": f"知乎回答「{topic}是什么？有什么影响？」，300字以上深度分析",
        "抖音": f"抖音发布 {topic} 相关短视频，前3秒设置话题钩子",
        "Twitter": f"Twitter 发布关于 {topic} 的英文评论，附相关 hashtag"
    }

    for platform in platforms:
        if platform in platform_suggestions:
            priority = "高优先级" if heat_level in ("hot", "trending") else "普通优先级"
            opportunities.append(f"[{priority}] {platform_suggestions[platform]}")

    if heat_level == "cold":
        opportunities.append(f"⏳ [{topic}] 当前热度较低，可考虑提前布局长尾内容")

    return opportunities


def generate_content_calendar(
    topic: str,
    heat_score: float,
    days: int = 7
) -> list[dict]:
    """
    生成未来 N 天的内容发布日历建议。
    
    Returns:
        list of {day, platform, content_type, priority}
    """
    topic = _sanitize(topic)
    calendar = []
    # 热度越高，发布频率越高
    publish_days = max(1, int(heat_score * days))
    day_interval = max(1, days // publish_days)

    platform_rotation = CONTENT_OPPORTUNITY_PLATFORMS * (days // len(CONTENT_OPPORTUNITY_PLATFORMS) + 1)

    for i in range(min(publish_days, days)):
        day = i * day_interval + 1
        platform = platform_rotation[i % len(platform_rotation)]
        calendar.append({
            "day": day,
            "platform": platform,
            "content_type": "图文" if platform in ("小红书", "微博") else "视频" if platform == "抖音" else "长文",
            "topic": topic,
            "priority": "high" if heat_score >= 0.7 else "medium"
        })

    return calendar
