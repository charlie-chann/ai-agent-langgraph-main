# tools/tag_optimizer.py — 知乎标签优化
from __future__ import annotations

import re
from dataclasses import dataclass

_TAG_POOL: dict[str, int] = {
    "职业发展": 8000, "科技前沿": 7500, "读书笔记": 6000, "人工智能": 9000,
    "投资理财": 7000, "心理学": 6500, "教育": 7000, "编程": 8500,
    "职场经验": 7200, "学习方法": 6800, "求职面试": 7100, "个人成长": 8200,
    "健康科普": 5500, "人际关系": 6000, "认知心理": 5800,
}


@dataclass
class TagResult:
    platform: str
    recommended_tags: list[str]
    trending_tags: list[str]
    niche_tags: list[str]
    engagement_score: float

    def to_dict(self) -> dict:
        return {
            "平台": self.platform,
            "推荐标签": self.recommended_tags,
            "热门标签": self.trending_tags,
            "细分标签": self.niche_tags,
            "预估互动得分": round(self.engagement_score, 1),
        }


def optimize_tags(platform: str, topic: str, keywords: list[str] | None = None, max_tags: int = 5) -> TagResult:
    """推荐最优标签组合。"""
    topic_clean = re.sub(r'[^\w\u4e00-\u9fff]', '', topic)[:20]
    keywords = [re.sub(r'[^\w\u4e00-\u9fff]', '', k)[:20] for k in (keywords or [])]

    sorted_tags = sorted(_TAG_POOL.items(), key=lambda x: x[1], reverse=True)
    top_n = max(1, len(sorted_tags) // 5)
    trending = [t[0] for t in sorted_tags[:top_n]]
    related = [t[0] for t in sorted_tags if any(kw in t[0] for kw in keywords + [topic_clean])]
    niche = [t for t in related if t not in trending]

    recommended = trending[:2] + niche[:max_tags - 2]
    for t, _ in sorted_tags:
        if t not in recommended:
            recommended.append(t)
        if len(recommended) >= max_tags:
            break
    recommended = recommended[:max_tags]

    avg_heat = sum(_TAG_POOL.get(t, 1000) for t in recommended) / max(len(recommended), 1)
    engagement = min(100.0, avg_heat / 1000)

    return TagResult(
        platform=platform,
        recommended_tags=recommended,
        trending_tags=trending[:3],
        niche_tags=niche[:5],
        engagement_score=engagement,
    )
