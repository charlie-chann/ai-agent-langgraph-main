# tools/content_generator.py — 微博内容生成工具
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from config import MAX_CONTENT_LENGTH, MAX_TAGS, PLATFORM, PROHIBITED_WORDS_CHECK


# 违禁词列表（简化示例）
_PROHIBITED_WORDS = [
    "赌博", "诈骗", "传销", "洗钱", "毒品", "走私", "假冒伪劣",
]

# 微博热门话题模板（按行业/领域）
_TOPIC_HASHTAGS: dict[str, list[str]] = {
    "科技": ["#AI技术#", "#人工智能#", "#科技资讯#", "#数字化转型#", "#技术分享#"],
    "生活": ["#生活分享#", "#日常记录#", "#美好生活#", "#生活态度#", "#随手拍#"],
    "美食": ["#美食探店#", "#吃货日常#", "#美食推荐#", "#下厨房#", "#家常菜#"],
    "旅行": ["#旅行攻略#", "#打卡地#", "#旅途记录#", "#出行日记#", "#风景如画#"],
    "健身": ["#健身打卡#", "#运动日记#", "#减脂增肌#", "#跑步#", "#健康生活#"],
    "职场": ["#职场干货#", "#职业发展#", "#工作感悟#", "#打工人#", "#成长记录#"],
    "教育": ["#学习打卡#", "#知识分享#", "#读书笔记#", "#自我提升#", "#每日学习#"],
    "财经": ["#财经资讯#", "#投资理财#", "#经济观察#", "#股市分析#", "#理财規划#"],
}


@dataclass
class WeiboPost:
    """微博帖子数据类。"""
    content: str
    hashtags: list[str]
    topic: str
    word_count: int
    scheduled_time: str = ""
    compliance_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "平台": PLATFORM,
            "内容": self.content,
            "话题标签": self.hashtags,
            "领域": self.topic,
            "字数": self.word_count,
            "发布时间": self.scheduled_time,
            "合规检查": self.compliance_check,
        }


def _check_compliance(text: str) -> dict:
    """内容合规检查。"""
    if not PROHIBITED_WORDS_CHECK:
        return {"passed": True, "violations": []}
    violations = [w for w in _PROHIBITED_WORDS if w in text]
    return {"passed": len(violations) == 0, "violations": violations}


def _sanitize_content(text: str) -> str:
    """清洗内容，移除潜在注入。"""
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    return text[:MAX_CONTENT_LENGTH * 2]  # 先不截断，生成后再截断


def generate_weibo_post(
    topic: str,
    keywords: list[str] | None = None,
    tone: str = "conversational",  # "conversational" | "professional" | "humorous"
    include_emoji: bool = True,
    custom_hashtags: list[str] | None = None,
) -> WeiboPost:
    """
    生成微博帖子内容（模板驱动，离线生成无需 LLM）。

    Args:
        topic: 内容领域（科技/生活/美食等）
        keywords: 核心关键词列表
        tone: 写作风格
        include_emoji: 是否包含 emoji
        custom_hashtags: 自定义话题标签

    Returns:
        WeiboPost
    """
    topic = _sanitize_content(topic)[:30]
    keywords = [_sanitize_content(k)[:20] for k in (keywords or [])[:5]]

    # 选择话题标签
    base_tags = _TOPIC_HASHTAGS.get(topic, _TOPIC_HASHTAGS["生活"])
    all_tags = (custom_hashtags or []) + base_tags
    selected_tags = all_tags[:MAX_TAGS]

    # 内容模板（按风格选择）
    kw_str = "、".join(keywords) if keywords else topic
    emoji_map = {"科技": "🚀", "生活": "✨", "美食": "🍜", "旅行": "✈️",
                 "健身": "💪", "职场": "📊", "教育": "📚", "财经": "💰"}
    em = emoji_map.get(topic, "💡") if include_emoji else ""

    if tone == "conversational":
        body = (
            f"{em} 今天和大家聊聊{kw_str}相关的内容！"
            f"在{topic}领域，有些事情真的很值得关注。"
            f"无论你是新手还是老手，总能找到适合自己的方向。"
            f"你有什么看法？欢迎评论区交流 👇"
        )
    elif tone == "professional":
        body = (
            f"【{topic}深度解析】{em}\n"
            f"关于{kw_str}，行业内有几个关键趋势值得关注：\n"
            f"1⃣ 技术迭代加速，应用场景不断拓宽\n"
            f"2⃣ 用户需求升级，精细化运营成主流\n"
            f"3⃣ 数据驱动决策，效率大幅提升"
        )
    else:  # humorous
        body = (
            f"哈哈哈，{kw_str}这事儿太有意思了 {em}\n"
            f"你们懂吗，在{topic}这个圈子里，不努力不行啊！\n"
            f"话说回来，大家有没有类似的经历？\n"
            f"评论区见，不吹不黑，就聊聊经验 🤣"
        )

    # 加入标签在结尾
    tag_str = " ".join(selected_tags[:3])
    content = f"{body} {tag_str}"

    # 截断到平台限制
    if len(content) > MAX_CONTENT_LENGTH:
        # 保留标签，截断正文
        content = body[:MAX_CONTENT_LENGTH - len(tag_str) - 5] + "… " + tag_str

    compliance = _check_compliance(content)

    from config import OPTIMAL_POST_HOURS
    from datetime import datetime
    now = datetime.now()
    next_hour = min((h for h in OPTIMAL_POST_HOURS if h >= now.hour), default=OPTIMAL_POST_HOURS[0])
    scheduled = f"{date.today()} {next_hour:02d}:00"

    return WeiboPost(
        content=content,
        hashtags=selected_tags,
        topic=topic,
        word_count=len(content),
        scheduled_time=scheduled,
        compliance_check=compliance,
    )


def generate_batch(topic: str, count: int = 3, tones: list[str] | None = None) -> list[WeiboPost]:
    """批量生成多条帖子。"""
    tones = tones or ["conversational", "professional", "humorous"]
    count = min(count, 10)  # 限制批量数量
    posts = []
    for i in range(count):
        tone = tones[i % len(tones)]
        posts.append(generate_weibo_post(topic, tone=tone))
    return posts
