"""RSS 采集工具 - 从多个 RSS 源获取最新文章"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MAX_ARTICLES_PER_SOURCE, SUMMARY_MAX_LENGTH


@dataclass
class RSSArticle:
    """RSS 文章数据结构"""
    title: str
    url: str
    source: str
    category: str
    published_at: str
    summary: str
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0


def _sanitize_text(text: str) -> str:
    """清洗文本：去除 HTML 标签、多余空白"""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "…" if len(text) > max_len else text


def fetch_rss_articles(
    source_url: str,
    source_name: str,
    category: str = "其他",
    tags: list[str] | None = None,
    max_articles: int = MAX_ARTICLES_PER_SOURCE
) -> list[RSSArticle]:
    """
    从 RSS URL 获取文章列表（模拟实现，不依赖外部网络）。
    生产环境中替换为 feedparser 实现。
    """
    tags = tags or []
    # 模拟数据：基于 source_name 生成占位文章
    mock_articles = [
        RSSArticle(
            title=f"[{source_name}] 头条新闻 {i+1}：AI 技术深度分析",
            url=f"https://example.com/{source_name.lower().replace(' ', '-')}/article-{i+1}",
            source=source_name,
            category=category,
            published_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            summary=_truncate(
                f"这是来自 {source_name} 的第 {i+1} 篇文章摘要。主要讨论当前热点话题与技术趋势。",
                SUMMARY_MAX_LENGTH
            ),
            tags=tags,
            relevance_score=round(0.9 - i * 0.1, 2)
        )
        for i in range(min(max_articles, 3))
    ]
    return mock_articles


def rank_articles(articles: list[RSSArticle]) -> list[RSSArticle]:
    """按相关性分数降序排列文章"""
    return sorted(articles, key=lambda a: a.relevance_score, reverse=True)


def filter_duplicates(articles: list[RSSArticle]) -> list[RSSArticle]:
    """基于标题相似性去重（简单版本：完全相同标题去重）"""
    seen_titles: set[str] = set()
    unique = []
    for article in articles:
        normalized = re.sub(r"\s+", " ", article.title.lower().strip())
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(article)
    return unique


def collect_from_sources(
    sources: list[dict],
    max_per_source: int = MAX_ARTICLES_PER_SOURCE
) -> list[RSSArticle]:
    """批量从多个 RSS 源采集文章"""
    all_articles: list[RSSArticle] = []
    for source in sources:
        if not source.get("enabled", True):
            continue
        articles = fetch_rss_articles(
            source_url=source["url"],
            source_name=source["name"],
            category=source.get("category", "其他"),
            tags=source.get("tags", []),
            max_articles=max_per_source
        )
        all_articles.extend(articles)

    all_articles = filter_duplicates(all_articles)
    all_articles = rank_articles(all_articles)
    return all_articles
