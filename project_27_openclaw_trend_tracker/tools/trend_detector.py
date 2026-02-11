"""趋势检测工具 - 监控话题热度变化"""

import re
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    HEAT_SCORE_DECAY, MIN_MENTIONS_FOR_TREND,
    HEAT_LEVELS, ALERT_THRESHOLD
)


@dataclass
class TrendSignal:
    """单个趋势信号"""
    topic: str
    keyword: str
    mentions: int
    heat_score: float         # 0-1，综合热度
    source: str               # 来源平台
    detected_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    momentum: float = 0.0     # 热度变化速度（正 = 上升，负 = 下降）


@dataclass
class TrendReport:
    """话题趋势报告"""
    topic: str
    heat_level: str           # cold / warming / hot / trending
    heat_score: float
    momentum: float
    top_signals: list[TrendSignal]
    alert: bool               # 是否触发预警
    summary: str
    content_opportunities: list[str]
    analyzed_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _sanitize_topic(topic: str) -> str:
    topic = re.sub(r"[\"'\\<>]", "", topic)
    return topic.strip()[:100]


def classify_heat_level(score: float) -> str:
    """将热度分数转为级别标签"""
    for level, (low, high) in HEAT_LEVELS.items():
        if low <= score < high:
            return level
    return "trending" if score >= 1.0 else "cold"


def compute_momentum(current: float, previous: float) -> float:
    """计算热度变化动量"""
    if previous == 0:
        return 0.0
    return round((current - previous) / previous, 3)


def apply_decay(score: float, hours_elapsed: float) -> float:
    """对旧信号应用热度衰减"""
    decayed = score * (HEAT_SCORE_DECAY ** hours_elapsed)
    return round(max(0.0, min(1.0, decayed)), 3)


def detect_trend_signals(
    topic: str,
    keywords: list[str] | None = None
) -> list[TrendSignal]:
    """
    检测话题的趋势信号（模拟多平台监控）。
    生产环境中接入 Tavily / 微博热搜 API / Twitter API。
    """
    topic = _sanitize_topic(topic)
    keywords = keywords or [topic]
    signals: list[TrendSignal] = []
    platforms_data = [
        ("news", 0.85, 12),
        ("weibo", 0.72, 8),
        ("wechat", 0.68, 5),
        ("douyin", 0.60, 15),
        ("twitter", 0.55, 6),
    ]
    for i, (platform, base_score, mentions) in enumerate(platforms_data):
        if mentions >= MIN_MENTIONS_FOR_TREND:
            # 模拟不同关键词的热度值
            keyword = keywords[i % len(keywords)]
            heat = round(base_score - i * 0.05, 2)
            momentum = round(0.1 - i * 0.03, 3)
            signals.append(TrendSignal(
                topic=topic,
                keyword=keyword,
                mentions=mentions,
                heat_score=max(0.1, heat),
                source=platform,
                momentum=momentum
            ))
    return signals


def compute_composite_heat(signals: list[TrendSignal]) -> float:
    """加权平均各平台热度，计算综合热度"""
    from config import SOURCE_WEIGHT
    if not signals:
        return 0.0
    weighted_sum = sum(
        s.heat_score * SOURCE_WEIGHT.get(s.source, 0.5)
        for s in signals
    )
    total_weight = sum(SOURCE_WEIGHT.get(s.source, 0.5) for s in signals)
    return round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
