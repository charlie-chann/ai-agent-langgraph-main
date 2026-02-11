"""内容适配器 - 将原始内容改写为各平台版本"""

import re
from dataclasses import dataclass, field
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PLATFORM_SPECS, ADAPTATION_STYLES


@dataclass
class AdaptedContent:
    """适配后的平台内容"""
    platform: str
    title: str
    body: str
    hashtags: list[str]
    char_count: int
    tone: str
    format_type: str
    compliant: bool          # 是否符合平台规范


def _sanitize_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate_to(text: str, max_chars: int) -> str:
    return text[:max_chars] + "…" if len(text) > max_chars else text


def _extract_key_points(content: str, max_points: int = 5) -> list[str]:
    """从长文中提取关键句（简单实现：取前N个完整句子）"""
    # 按句子分割
    sentences = re.split(r"[。！？\.!?]", content)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
    return sentences[:max_points]


def _generate_hashtags(topic: str, platform: str, count: int) -> list[str]:
    """为内容生成话题标签"""
    if count == 0:
        return []

    # 基于话题生成模拟标签池
    tag_pools = {
        "weibo": [f"#{topic}#", "#热门话题#", "#今日推荐#", "#好文分享#", "#知识#"],
        "xiaohongshu": [f"#{topic}", "#干货分享", "#知识博主", "#学习笔记", "#内容推荐"],
        "douyin": [f"#{topic}", "#知识分享", "#干货", "#涨知识", "#今日推荐"],
        "twitter": [topic.replace(" ", ""), "AI", "Tech", "Innovation", "Insights"],
        "zhihu": []
    }
    tags = tag_pools.get(platform, [topic])
    return tags[:count]


def adapt_to_weibo(content: str, topic: str) -> AdaptedContent:
    """将内容适配为微博风格"""
    spec = PLATFORM_SPECS["weibo"]
    points = _extract_key_points(content, 3)
    body = "📌 " + "\n\n".join(points[:2]) if points else content
    body = _truncate_to(body, spec["max_chars"])
    hashtags = _generate_hashtags(topic, "weibo", spec["hashtag_count"])
    return AdaptedContent(
        platform="weibo",
        title=f"{topic}——你必须知道的事",
        body=body,
        hashtags=hashtags,
        char_count=len(body),
        tone=spec["tone"],
        format_type=spec["format"],
        compliant=len(body) <= spec["max_chars"]
    )


def adapt_to_xiaohongshu(content: str, topic: str) -> AdaptedContent:
    """将内容适配为小红书风格"""
    spec = PLATFORM_SPECS["xiaohongshu"]
    points = _extract_key_points(content, 3)
    lines = [f"✨ {topic}｜干货来了！", "", "💡 核心要点："]
    for i, p in enumerate(points[:3], 1):
        lines.append(f"{i}. {p}")
    body = "\n".join(lines)
    body = _truncate_to(body, spec["max_chars"])
    hashtags = _generate_hashtags(topic, "xiaohongshu", spec["hashtag_count"])
    return AdaptedContent(
        platform="xiaohongshu",
        title=f"「{topic}」深度解析｜建议收藏",
        body=body,
        hashtags=hashtags,
        char_count=len(body),
        tone=spec["tone"],
        format_type=spec["format"],
        compliant=len(body) <= spec["max_chars"]
    )


def adapt_to_zhihu(content: str, topic: str) -> AdaptedContent:
    """将内容适配为知乎风格（深度分析）"""
    spec = PLATFORM_SPECS["zhihu"]
    points = _extract_key_points(content, 5)
    sections = [f"## 关于{topic}的深度分析", "", content[:1000]]
    if points:
        sections += ["", "## 核心观点"]
        for p in points:
            sections.append(f"- {p}")
    body = "\n".join(sections)
    body = _truncate_to(body, spec["max_chars"])
    return AdaptedContent(
        platform="zhihu",
        title=f"如何深度理解{topic}？",
        body=body,
        hashtags=[],
        char_count=len(body),
        tone=spec["tone"],
        format_type=spec["format"],
        compliant=len(body) <= spec["max_chars"]
    )


def adapt_to_douyin(content: str, topic: str) -> AdaptedContent:
    """将内容适配为抖音视频脚本"""
    spec = PLATFORM_SPECS["douyin"]
    points = _extract_key_points(content, 3)
    hook = f"你知道关于{topic}，有一件事大多数人都搞错了吗？"
    main_points = "".join([f"第{i+1}点，{p}。 " for i, p in enumerate(points[:2])])
    cta = f"关注我，每天分享{topic}干货！"
    body = f"{hook}\n\n{main_points}\n\n{cta}"
    body = _truncate_to(body, spec["max_chars"])
    hashtags = _generate_hashtags(topic, "douyin", spec["hashtag_count"])
    return AdaptedContent(
        platform="douyin",
        title=f"{topic}，99%的人不知道这件事",
        body=body,
        hashtags=hashtags,
        char_count=len(body),
        tone=spec["tone"],
        format_type=spec["format"],
        compliant=len(body) <= spec["max_chars"]
    )


def adapt_to_twitter(content: str, topic: str) -> AdaptedContent:
    """将内容适配为 Twitter 推文"""
    spec = PLATFORM_SPECS["twitter"]
    points = _extract_key_points(content, 3)
    # Take first meaningful point (or truncate content)
    first_point = points[0] if points else content[:150]
    first_point_en = first_point[:180]  # simplified for demo (no real translation)
    body = f"{first_point_en}"
    body = _truncate_to(body, spec["max_chars"] - 30)  # leave room for hashtags
    hashtags = _generate_hashtags(topic, "twitter", spec["hashtag_count"])
    return AdaptedContent(
        platform="twitter",
        title=f"On {topic}:",
        body=body,
        hashtags=hashtags,
        char_count=len(body),
        tone=spec["tone"],
        format_type=spec["format"],
        compliant=len(body) <= spec["max_chars"]
    )


ADAPTERS = {
    "weibo": adapt_to_weibo,
    "xiaohongshu": adapt_to_xiaohongshu,
    "zhihu": adapt_to_zhihu,
    "douyin": adapt_to_douyin,
    "twitter": adapt_to_twitter
}


def repurpose_for_platform(content: str, topic: str, platform: str) -> AdaptedContent | None:
    """将内容适配为指定平台格式"""
    content = _sanitize_text(content)
    topic = _sanitize_text(topic)
    adapter = ADAPTERS.get(platform)
    if not adapter:
        return None
    return adapter(content, topic)


def repurpose_for_all_platforms(content: str, topic: str, platforms: list[str] | None = None) -> dict[str, AdaptedContent]:
    """将内容批量适配为所有目标平台"""
    from config import DEFAULT_TARGET_PLATFORMS
    platforms = platforms or DEFAULT_TARGET_PLATFORMS
    results = {}
    for platform in platforms:
        adapted = repurpose_for_platform(content, topic, platform)
        if adapted:
            results[platform] = adapted
    return results
