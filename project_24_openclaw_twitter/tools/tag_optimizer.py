# tools/tag_optimizer.py — Twitter 标签优化
from __future__ import annotations

import re
from dataclasses import dataclass

_TAG_POOL: dict[str, int] = {
    "AI": 95000, "Tech": 85000, "Python": 45000, "MachineLearning": 55000,
    "Startup": 40000, "Productivity": 38000, "OpenAI": 62000, "LLM": 48000,
    "Developer": 52000, "OpenSource": 42000, "DataScience": 50000,
    "Career": 35000, "Finance": 30000, "BuildInPublic": 28000, "IndieHacker": 25000,
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


def optimize_tags(platform: str, topic: str, keywords: list[str] | None = None, max_tags: int = 3) -> TagResult:
    """推荐最优标签组合（Twitter最多3个）。"""
    topic_clean = re.sub(r'[^\w]', '', topic)[:30]
    keywords = [re.sub(r'[^\w]', '', k)[:20] for k in (keywords or [])]

    sorted_tags = sorted(_TAG_POOL.items(), key=lambda x: x[1], reverse=True)
    top_n = max(1, len(sorted_tags) // 5)
    trending = [t[0] for t in sorted_tags[:top_n]]
    related = [t[0] for t in sorted_tags if any(kw.lower() in t[0].lower() for kw in keywords + [topic_clean])]
    niche = [t for t in related if t not in trending]

    recommended = trending[:1] + niche[:max_tags - 1]
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
