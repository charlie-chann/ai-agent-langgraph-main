# tools/content_generator.py — 小红书内容生成（图文笔记）
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from config import MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH, MAX_TAGS, PLATFORM, PROHIBITED_WORDS_CHECK


_PROHIBITED_WORDS = ["赌博", "诈骗", "传销", "假冒伪劣", "违禁"]

_TOPIC_HASHTAGS: dict[str, list[str]] = {
    "美妆": ["护肤心得", "好物分享", "美妆教程", "素颜神器", "skincare"],
    "穿搭": ["穿搭分享", "outfit", "时尚穿搭", "学生穿搭", "通勤穿搭"],
    "美食": ["美食分享", "下厨笔记", "食谱", "美食探店", "家常菜"],
    "健身": ["健身打卡", "减脂日记", "运动穿搭", "练出好身材", "健康生活"],
    "旅行": ["旅行攻略", "打卡", "旅游分享", "小众景点", "国内旅行"],
    "学习": ["学习干货", "考研打卡", "读书笔记", "自律打卡", "知识分享"],
    "职场": ["职场干货", "求职技巧", "职业规划", "工作心得", "副业"],
    "科技": ["科技好物", "数码测评", "AI工具", "效率工具", "好用软件"],
}

_SECTION_EMOJIS = ["✨", "💡", "🌟", "📌", "🎯", "💪", "🔥", "🌸"]


@dataclass
class XiaohongshuPost:
    """小红书笔记数据类。"""
    title: str
    content: str
    hashtags: list[str]
    topic: str
    image_suggestions: list[str]   # 图片拍摄建议
    word_count: int
    compliance_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "平台": PLATFORM,
            "标题": self.title,
            "正文": self.content,
            "标签": self.hashtags,
            "领域": self.topic,
            "配图建议": self.image_suggestions,
            "字数": self.word_count,
            "合规检查": self.compliance_check,
        }


def _check_compliance(text: str) -> dict:
    violations = [w for w in _PROHIBITED_WORDS if w in text] if PROHIBITED_WORDS_CHECK else []
    return {"passed": len(violations) == 0, "violations": violations}


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    return re.sub(r'<[^>]+>', '', text)


def generate_xiaohongshu_post(
    topic: str,
    keywords: list[str] | None = None,
    style: str = "lifestyle",  # "lifestyle" | "tutorial" | "review"
) -> XiaohongshuPost:
    """生成小红书图文笔记。"""
    topic = _sanitize(topic)[:30]
    keywords = [_sanitize(k)[:20] for k in (keywords or [])[:5]]
    kw_str = "、".join(keywords) if keywords else topic

    # 标题（吸睛 + 关键词）
    title_templates = {
        "lifestyle": f"分享我的{topic}日常 | {kw_str}真的绝了✨",
        "tutorial": f"保姆级{topic}教程 | 新手也能轻松搞定🎯",
        "review": f"用了3个月的{topic}，说说我的真实感受💡",
    }
    title = title_templates.get(style, title_templates["lifestyle"])
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH - 1] + "…"

    # 正文（结构化分段）
    em = _SECTION_EMOJIS[len(topic) % len(_SECTION_EMOJIS)]
    if style == "tutorial":
        body = (
            f"{em} **前言**\n"
            f"很多小伙伴问我关于{kw_str}的问题，今天来做个详细分享！\n\n"
            f"📋 **所需材料/准备**\n"
            f"- 基础工具一套\n- 备好耐心和时间\n\n"
            f"✅ **步骤详解**\n"
            f"step1: 首先做好准备工作\n"
            f"step2: 按照顺序一步步来\n"
            f"step3: 注意细节，做好收尾\n\n"
            f"💬 **小贴士**\n"
            f"新手常犯的错误就是{kw_str}时太心急，一定要稳！\n\n"
            f"如果有任何问题，欢迎评论区留言~"
        )
        images = ["操作过程步骤图", "成品展示图", "工具材料平铺图"]
    elif style == "review":
        body = (
            f"{em} **购入原因**\n"
            f"之前一直在找适合自己的{kw_str}，试了很多终于遇到这款！\n\n"
            f"📦 **开箱体验**\n"
            f"包装精心，第一眼就很有好感~\n\n"
            f"⭐ **使用感受**\n"
            f"优点：效果显著，使用方便\n"
            f"缺点：价格稍高，需要坚持使用\n\n"
            f"💰 **值得买吗？**\n"
            f"个人认为{kw_str}的性价比还是不错的，推荐给同款需求的小伙伴！"
        )
        images = ["产品正面图", "使用前后对比图", "细节特写图"]
    else:  # lifestyle
        body = (
            f"{em} 最近迷上了{kw_str}，来和大家分享一下日常！\n\n"
            f"🌟 **为什么喜欢**\n"
            f"生活中有了{topic}，整个人都精神了许多，效率提升不止一点点~\n\n"
            f"📷 **日常记录**\n"
            f"每天坚持打卡，已经{(len(topic) % 30) + 7}天了！给自己鼓个掌👏\n\n"
            f"💭 **感想**\n"
            f"希望大家都能找到属于自己的节奏，一起努力！"
        )
        images = ["日常生活场景图", "物品摆拍图", "氛围感照片"]

    # 截断
    if len(body) > MAX_CONTENT_LENGTH:
        body = body[:MAX_CONTENT_LENGTH - 3] + "..."

    tags = _TOPIC_HASHTAGS.get(topic, ["种草", "好物推荐", "生活分享"])[:MAX_TAGS]
    compliance = _check_compliance(title + body)

    return XiaohongshuPost(
        title=title,
        content=body,
        hashtags=tags,
        topic=topic,
        image_suggestions=images,
        word_count=len(title) + len(body),
        compliance_check=compliance,
    )
