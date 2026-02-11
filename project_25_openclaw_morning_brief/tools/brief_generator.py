"""早报生成工具 - 将文章列表转化为格式化早报"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MAX_BRIEF_LENGTH, TOP_STORIES_COUNT, SUMMARY_MAX_LENGTH, CATEGORIES
from tools.rss_collector import RSSArticle


@dataclass
class MorningBrief:
    """早报数据结构"""
    date: str
    title: str
    headline_count: int
    sections: dict[str, list[dict]]   # category -> list of article dicts
    top_stories: list[dict]           # 精选头条
    summary: str                      # 一句话总结
    word_count: int = 0
    format: str = "markdown"
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _article_to_dict(article: RSSArticle) -> dict:
    return {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "summary": article.summary,
        "published_at": article.published_at,
        "relevance_score": article.relevance_score
    }


def group_by_category(articles: list[RSSArticle]) -> dict[str, list[RSSArticle]]:
    """按分类分组文章"""
    groups: dict[str, list[RSSArticle]] = {cat: [] for cat in CATEGORIES}
    for article in articles:
        cat = article.category if article.category in groups else "其他"
        groups[cat].append(article)
    # 去除空分类
    return {k: v for k, v in groups.items() if v}


def generate_brief_markdown(brief: MorningBrief) -> str:
    """生成 Markdown 格式早报"""
    lines = [
        f"# {brief.title}",
        f"> {brief.date} | 共 {brief.headline_count} 条资讯 | 生成时间: {brief.generated_at}",
        "",
        f"**今日速览：** {brief.summary}",
        "",
        "---",
        "",
        "## 🌟 精选头条",
        ""
    ]
    for i, story in enumerate(brief.top_stories[:TOP_STORIES_COUNT], 1):
        lines.append(f"{i}. **[{story['title']}]({story['url']})** — {story['source']}")
        lines.append(f"   > {story['summary']}")
        lines.append("")

    lines += ["---", ""]
    for cat, articles in brief.sections.items():
        if not articles:
            continue
        emoji_map = {
            "国际要闻": "🌍",
            "科技动态": "💻",
            "财经市场": "📈",
            "国内新闻": "🏮",
            "其他": "📰"
        }
        emoji = emoji_map.get(cat, "📰")
        lines.append(f"## {emoji} {cat}")
        lines.append("")
        for article in articles:
            lines.append(f"- **[{article['title']}]({article['url']})** ({article['source']})")
            lines.append(f"  {article['summary']}")
        lines.append("")

    return "\n".join(lines)


def generate_brief_plain(brief: MorningBrief) -> str:
    """生成纯文本格式早报"""
    lines = [
        f"【{brief.title}】",
        f"{brief.date} | {brief.headline_count}条资讯",
        f"今日速览：{brief.summary}",
        "",
        "=== 精选头条 ==="
    ]
    for i, story in enumerate(brief.top_stories[:TOP_STORIES_COUNT], 1):
        lines.append(f"{i}. {story['title']} [{story['source']}]")
        lines.append(f"   {story['summary']}")
    return "\n".join(lines)


def create_morning_brief(
    articles: list[RSSArticle],
    date: str | None = None,
    output_format: Literal["markdown", "plain", "html"] = "markdown"
) -> MorningBrief:
    """从文章列表生成早报对象"""
    if not date:
        date = datetime.now().strftime("%Y年%m月%d日")

    grouped = group_by_category(articles)
    sections = {cat: [_article_to_dict(a) for a in items] for cat, items in grouped.items()}
    top_stories = [_article_to_dict(a) for a in articles[:TOP_STORIES_COUNT]]

    # 生成一句话日期概要
    source_names = list({a.source for a in articles[:5]})
    summary = f"来自 {', '.join(source_names[:3])} 等 {len(set(a.source for a in articles))} 个来源的 {len(articles)} 条资讯已为您整理完毕。"

    brief = MorningBrief(
        date=date,
        title=f"📰 {date} 今日早报",
        headline_count=len(articles),
        sections=sections,
        top_stories=top_stories,
        summary=summary,
        format=output_format
    )

    if output_format == "markdown":
        content = generate_brief_markdown(brief)
    else:
        content = generate_brief_plain(brief)
    brief.word_count = len(content)
    return brief


def format_brief_for_display(brief: MorningBrief) -> str:
    """返回用于界面展示的格式化字符串"""
    if brief.format == "markdown":
        return generate_brief_markdown(brief)
    return generate_brief_plain(brief)
