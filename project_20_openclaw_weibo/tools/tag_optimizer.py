# tools/tag_optimizer.py — 话题标签优化工具（共用于 openclaw 系列）
from __future__ import annotations

import re
from dataclasses import dataclass


# 各平台热门标签词频数据库（简化）
_TAG_POOLS: dict[str, dict[str, int]] = {
    "weibo": {
        "AI技术": 9800, "人工智能": 12000, "科技资讯": 8500, "数字化转型": 6000,
        "生活分享": 15000, "日常记录": 11000, "打工人": 18000, "职场干货": 9000,
        "美食探店": 13000, "旅行攻略": 11000, "健身打卡": 9500,
    },
    "xiaohongshu": {
        "好物推荐": 20000, "种草": 25000, "生活方式": 18000, "穿搭": 22000,
        "护肤": 19000, "减脂": 16000, "学习打卡": 14000, "职场穿搭": 12000,
    },
    "zhihu": {
        "职业发展": 8000, "科技前沿": 7500, "读书笔记": 6000, "人工智能": 9000,
        "投资理财": 7000, "心理学": 6500, "教育": 7000,
    },
    "douyin": {
        "知识分享": 50000, "生活技巧": 45000, "美食教程": 55000, "健身打卡": 40000,
        "职场技能": 35000, "搞笑": 60000, "正能量": 42000, "成长": 38000,
    },
    "twitter": {
        "AI": 95000, "Tech": 85000, "Python": 45000, "MachineLearning": 55000,
        "Startup": 40000, "Productivity": 38000, "OpenAI": 62000,
    },
}


@dataclass
class TagResult:
    """标签优化结果。"""
    platform: str
    recommended_tags: list[str]
    trending_tags: list[str]
    niche_tags: list[str]
    engagement_score: float  # 预估互动得分 0-100

    def to_dict(self) -> dict:
        return {
            "平台": self.platform,
            "推荐标签": self.recommended_tags,
            "热门标签": self.trending_tags,
            "细分标签": self.niche_tags,
            "预估互动得分": round(self.engagement_score, 1),
        }


def optimize_tags(
    platform: str,
    topic: str,
    keywords: list[str] | None = None,
    max_tags: int = 5,
) -> TagResult:
    """
    为内容推荐最优话题标签组合。

    策略：混合热门标签（引流）+ 细分标签（精准受众）
    """
    topic_clean = re.sub(r'[^\w\u4e00-\u9fff]', '', topic)[:20]
    keywords = [re.sub(r'[^\w\u4e00-\u9fff]', '', k)[:20] for k in (keywords or [])]

    tag_pool = _TAG_POOLS.get(platform, _TAG_POOLS.get("weibo", {}))

    # 按热度排序
    sorted_tags = sorted(tag_pool.items(), key=lambda x: x[1], reverse=True)

    # 热门标签（前20%）
    top_n = max(1, len(sorted_tags) // 5)
    trending = [t[0] for t in sorted_tags[:top_n]]

    # 相关标签（含关键词的）
    related = [t[0] for t in sorted_tags if any(kw in t[0] for kw in keywords + [topic_clean])]
    niche = [t for t in related if t not in trending]

    # 混合策略：1-2 个热门 + 其余细分
    recommended = trending[:2] + niche[:max_tags - 2]
    if len(recommended) < max_tags:
        for t, _ in sorted_tags:
            if t not in recommended:
                recommended.append(t)
            if len(recommended) >= max_tags:
                break

    recommended = recommended[:max_tags]

    # 预估互动得分（简单加权平均）
    avg_heat = sum(tag_pool.get(t, 1000) for t in recommended) / max(len(recommended), 1)
    engagement = min(100.0, avg_heat / 1000)

    return TagResult(
        platform=platform,
        recommended_tags=recommended,
        trending_tags=trending[:3],
        niche_tags=niche[:5],
        engagement_score=engagement,
    )
