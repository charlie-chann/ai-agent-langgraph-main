# tools/content_generator.py — 知乎回答/专栏文章生成
from __future__ import annotations

import re
from dataclasses import dataclass, field
from config import MAX_ANSWER_LENGTH, MAX_ARTICLE_LENGTH, MAX_TAGS, PLATFORM, PROHIBITED_WORDS_CHECK


_PROHIBITED_WORDS = ["赌博", "诈骗", "传销", "违禁"]

_TOPIC_TAGS: dict[str, list[str]] = {
    "职场": ["职业发展", "职场经验", "求职面试", "薪资谈判", "工作效率"],
    "科技": ["人工智能", "编程", "软件开发", "技术趋势", "产品设计"],
    "教育": ["学习方法", "考研", "留学", "自学", "读书笔记"],
    "投资": ["理财", "投资策略", "股票", "基金", "个人财务"],
    "心理": ["心理健康", "情绪管理", "人际关系", "自我提升", "认知"],
    "医疗": ["健康科普", "营养", "运动健康", "医疗常识"],
}


@dataclass
class ZhihuContent:
    """知乎内容数据类。"""
    content_type: str   # "answer" | "article"
    title: str
    body: str
    tags: list[str]
    word_count: int
    estimated_upvotes: int   # 基于内容质量的预估点赞
    compliance_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "平台": PLATFORM,
            "类型": self.content_type,
            "标题/问题": self.title,
            "正文": self.body,
            "标签": self.tags,
            "字数": self.word_count,
            "预估点赞": self.estimated_upvotes,
            "合规检查": self.compliance_check,
        }


def _check_compliance(text: str) -> dict:
    violations = [w for w in _PROHIBITED_WORDS if w in text] if PROHIBITED_WORDS_CHECK else []
    return {"passed": len(violations) == 0, "violations": violations}


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    return re.sub(r'<[^>]+>', '', text)


def generate_zhihu_answer(question: str, topic: str,
                          expertise_level: str = "intermediate") -> ZhihuContent:
    """
    生成知乎回答。

    Args:
        question: 问题标题
        topic: 领域
        expertise_level: "beginner" | "intermediate" | "expert"
    """
    question = _sanitize(question)[:100]
    topic = _sanitize(topic)[:30]

    if expertise_level == "expert":
        body = (
            f"**结论先行**：关于「{question}」，我的回答是：这取决于你的具体情况，但有几个关键原则值得关注。\n\n"
            f"**深度分析**\n\n"
            f"在{topic}领域从事多年，见过太多类似的问题。\n\n"
            f"首先，我们需要拆解这个问题的本质。表面上看是{topic}问题，"
            f"但根本上是**资源分配**和**优先级判断**的问题。\n\n"
            f"**三个关键框架**\n\n"
            f"1. **框架一**：先确定你的目标，所有行动都服务于目标\n"
            f"2. **框架二**：评估你的资源（时间、精力、金钱），选择最优路径\n"
            f"3. **框架三**：设定阶段里程碑，及时调整策略\n\n"
            f"**常见误区**\n\n"
            f"很多人在这个问题上最大的错误是：试图找到「标准答案」，"
            f"却忽视了自身情况的特殊性。\n\n"
            f"**我的建议**\n\n"
            f"根据你描述的情况，建议先做 A，再做 B，"
            f"如果遇到 C 情况则转向 D 方案。\n\n"
            f"欢迎在评论区继续探讨，更多细节可以私信。"
        )
        est_upvotes = 150
    elif expertise_level == "beginner":
        body = (
            f"作为一个{topic}新手，分享一下我的理解和经验 😊\n\n"
            f"关于「{question}」，我觉得可以从以下几点来思考：\n\n"
            f"第一点，先搞清楚基础概念，这是一切的前提。\n\n"
            f"第二点，多实践，理论再好也不如动手尝试。\n\n"
            f"第三点，找到适合自己的方法，别人的经验做参考就好。\n\n"
            f"希望对你有帮助！如果有更好的见解欢迎补充~"
        )
        est_upvotes = 30
    else:  # intermediate
        body = (
            f"关于「{question}」，说说我的看法。\n\n"
            f"**背景**：在{topic}这个领域，这个问题其实很有代表性。\n\n"
            f"**核心观点**\n\n"
            f"> 没有放之四海而皆准的答案，关键在于找到适合自己的方式。\n\n"
            f"**具体来说**\n\n"
            f"☑ 首先，明确自己的需求和痛点\n"
            f"☑ 其次，了解主流方法的优缺点\n"
            f"☑ 最后，结合实际情况做出选择\n\n"
            f"**个人经验**\n\n"
            f"我在{topic}方面摸索了一段时间，发现最重要的是：**坚持**和**复盘**。\n\n"
            f"希望这个回答对你有所启发。"
        )
        est_upvotes = 75

    if len(body) > MAX_ANSWER_LENGTH:
        body = body[:MAX_ANSWER_LENGTH - 3] + "..."

    tags = _TOPIC_TAGS.get(topic, ["经验分享", "个人成长"])[:MAX_TAGS]
    compliance = _check_compliance(question + body)

    return ZhihuContent(
        content_type="answer",
        title=question,
        body=body,
        tags=tags,
        word_count=len(body),
        estimated_upvotes=est_upvotes,
        compliance_check=compliance,
    )
