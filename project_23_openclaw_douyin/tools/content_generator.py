# tools/content_generator.py — 抖音视频脚本生成
from __future__ import annotations

import re
from dataclasses import dataclass, field
from config import MAX_SCRIPT_LENGTH, MAX_TITLE_LENGTH, MAX_TAGS, PLATFORM, PROHIBITED_WORDS_CHECK, VIDEO_DURATIONS


_PROHIBITED_WORDS = ["赌博", "诈骗", "低俗", "违禁"]

_TOPIC_HASHTAGS: dict[str, list[str]] = {
    "知识": ["知识分享", "干货", "涨知识了", "学习打卡", "每日一学"],
    "美食": ["美食教程", "下厨房", "美食探店", "家常菜", "食谱分享"],
    "搞笑": ["搞笑日常", "哈哈哈", "生活趣事", "整活", "笑死我了"],
    "励志": ["正能量", "努力奋斗", "每天进步", "成长记录", "坚持"],
    "才艺": ["才艺展示", "手工DIY", "创意", "艺术", "表演"],
    "生活": ["生活记录", "vlog", "日常", "生活技巧", "居家好物"],
}

# 钩子开场白模板
_HOOK_TEMPLATES = [
    "你知道吗？{keyword}里有一个鲜为人知的秘密！",
    "同样在做{keyword}，为什么他们能成功而你不行？",
    "3秒告诉你{keyword}的致命误区，99%的人都犯过！",
    "我当初不知道{keyword}这件事，走了很多弯路……",
    "做{keyword}5年，今天把压箱底的经验分享给你！",
]


@dataclass
class DouyinScript:
    """抖音视频脚本数据类。"""
    title: str
    duration_seconds: int
    hook: str          # 开场钩子（前3秒）
    main_content: str  # 主体内容
    call_to_action: str  # 结尾引导
    hashtags: list[str]
    word_count: int
    compliance_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "平台": PLATFORM,
            "视频标题": self.title,
            "时长(秒)": self.duration_seconds,
            "开场钩子": self.hook,
            "主体内容": self.main_content,
            "结尾引导": self.call_to_action,
            "话题标签": self.hashtags,
            "脚本字数": self.word_count,
            "合规检查": self.compliance_check,
        }


def _check_compliance(text: str) -> dict:
    violations = [w for w in _PROHIBITED_WORDS if w in text] if PROHIBITED_WORDS_CHECK else []
    return {"passed": len(violations) == 0, "violations": violations}


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    return re.sub(r'<[^>]+>', '', text)


def generate_douyin_script(
    topic: str,
    keywords: list[str] | None = None,
    duration: int = 60,   # 秒
    style: str = "educational",  # "educational" | "entertaining" | "motivational"
) -> DouyinScript:
    """生成抖音视频脚本。"""
    topic = _sanitize(topic)[:30]
    keywords = [_sanitize(k)[:20] for k in (keywords or [])[:3]]
    kw = keywords[0] if keywords else topic

    # 标准化时长
    duration = min(VIDEO_DURATIONS, key=lambda d: abs(d - duration))

    # 钩子
    hook = _HOOK_TEMPLATES[len(topic) % len(_HOOK_TEMPLATES)].format(keyword=kw)

    # 主体（按时长调整）
    if duration <= 15:
        main = f"直接说重点：关于{kw}，最关键的一点是——{topic}核心就在于坚持和方法！"
    elif duration <= 30:
        main = (
            f"很多人对{kw}有误解。\n\n"
            f"实际上，{topic}的正确做法是：\n"
            f"第一，打好基础；第二，持续练习；第三，及时复盘。\n"
            f"记住这三点，你的{kw}水平会大幅提升！"
        )
    elif duration <= 60:
        main = (
            f"今天说{kw}，很多人都做错了。\n\n"
            f"【误区一】以为{topic}靠天分\n"
            f"真相：90%靠方法，10%靠天分\n\n"
            f"【误区二】急于求成\n"
            f"真相：罗马不是一天建成的，{kw}也需要时间积累\n\n"
            f"【正确做法】\n"
            f"步骤1：先建立基础认知\n"
            f"步骤2：找到适合自己的节奏\n"
            f"步骤3：坚持30天，你会看到质变！"
        )
    else:  # 180
        main = (
            f"关于{kw}，我研究了很久，今天做个系统总结。\n\n"
            f"**第一部分：为什么{topic}重要**\n"
            f"在当今时代，{kw}已经成为核心竞争力之一...\n\n"
            f"**第二部分：常见误区**\n"
            f"误区1、2、3（详细展开）\n\n"
            f"**第三部分：实操方法**\n"
            f"具体步骤，配合案例讲解...\n\n"
            f"**第四部分：总结**\n"
            f"记住这三个关键词：方向、方法、坚持"
        )

    # CTA
    cta_map = {
        "educational": "学到了记得点赞收藏！关注我，每天分享干货 👍",
        "entertaining": "觉得好玩的点个赞，评论区聊聊你的经历 😄",
        "motivational": "一起加油！转发给需要看到这条视频的朋友 🔥",
    }
    cta = cta_map.get(style, cta_map["educational"])

    if len(main) > MAX_SCRIPT_LENGTH:
        main = main[:MAX_SCRIPT_LENGTH - 3] + "..."

    tags = _TOPIC_HASHTAGS.get(topic, ["知识分享", "干货"])[:MAX_TAGS]
    full_text = hook + main + cta
    compliance = _check_compliance(full_text)

    title = f"{kw}竟然有这么多人不知道！"
    if len(title) > MAX_TITLE_LENGTH:
        title = title[:MAX_TITLE_LENGTH - 1] + "…"

    return DouyinScript(
        title=title,
        duration_seconds=duration,
        hook=hook,
        main_content=main,
        call_to_action=cta,
        hashtags=tags,
        word_count=len(full_text),
        compliance_check=compliance,
    )
