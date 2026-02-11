# tools/email_generator.py — 销售邮件生成工具（模板驱动，无需 LLM 调用）
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass
class SalesEmail:
    """销售邮件数据类。"""
    to_name: str
    to_company: str
    subject: str
    body: str
    email_type: str   # "first_contact" | "followup" | "proposal" | "nurture"

    def to_dict(self) -> dict:
        return {
            "收件人": f"{self.to_name} / {self.to_company}",
            "主题": self.subject,
            "正文": self.body,
            "邮件类型": self.email_type,
        }


_TEMPLATES: dict[str, dict] = {
    "first_contact": {
        "subject": "【{company}需求对接】{product}解决方案简介",
        "body": (
            "尊敬的{name}您好，\n\n"
            "我是{sender}，来自{sender_company}。\n\n"
            "了解到{company}在{industry}领域快速发展，我们的{product}解决方案已帮助同行业多家企业"
            "实现效率提升30%+。\n\n"
            "希望能与您安排一次20分钟的线上交流，了解贵公司当前的业务痛点。\n\n"
            "请问您本周或下周是否方便？\n\n"
            "祝商祺，\n{sender}\n{sender_company}"
        ),
    },
    "followup": {
        "subject": "Re: 关于{company}与{sender_company}的合作事宜",
        "body": (
            "尊敬的{name}您好，\n\n"
            "上次与您沟通后，我们针对{company}的需求整理了一份定制化方案。\n\n"
            "核心要点：\n"
            "1. 快速部署，{timeline}内完成上线\n"
            "2. 成本可控，预算在{budget}万元范围内\n"
            "3. 专属客户成功团队全程跟进\n\n"
            "期待您的回复，方便的话我们可以进一步细化方案。\n\n"
            "祝好，\n{sender}\n{sender_company}"
        ),
    },
    "proposal": {
        "subject": "【正式方案】{company} × {sender_company} 合作提案",
        "body": (
            "尊敬的{name}，\n\n"
            "感谢您抽时间了解我们的方案。附件为为{company}量身定制的完整合作提案，包含：\n\n"
            "• 业务痛点分析与解决路径\n"
            "• 产品演示视频及功能清单\n"
            "• 实施计划与时间表\n"
            "• 报价及付款方式\n\n"
            "若有任何疑问，请随时联系我。期待与{company}携手合作。\n\n"
            "诚挚地，\n{sender}\n{sender_company}"
        ),
    },
    "nurture": {
        "subject": "【行业洞察】{date}｜{industry}最新趋势分享",
        "body": (
            "尊敬的{name}您好，\n\n"
            "为您整理了{industry}领域本期最值得关注的3个趋势：\n\n"
            "1. 数字化转型加速，合规要求趋严\n"
            "2. AI 辅助决策已成主流企业标配\n"
            "3. 数据安全与隐私保护受到监管重视\n\n"
            "如您近期有相关采购计划，欢迎随时联系我们探讨。\n\n"
            "祝好，\n{sender}"
        ),
    },
}


def _sanitize_field(value: str, max_len: int = 100) -> str:
    """清洗模板变量，防止注入和 XSS。"""
    value = re.sub(r'[\x00-\x1f]', '', str(value))
    # 移除 HTML/script 标签
    value = re.sub(r'<[^>]*>', '', value)
    return value[:max_len]


def generate_email(
    email_type: str,
    to_name: str,
    to_company: str,
    industry: str,
    product: str = "AI 智能解决方案",
    sender: str = "销售顾问",
    sender_company: str = "智创科技",
    budget: float | None = None,
    timeline: str = "30天",
) -> SalesEmail:
    """
    根据邮件类型生成销售邮件。

    Args:
        email_type: "first_contact" | "followup" | "proposal" | "nurture"
        to_name: 收件人姓名
        to_company: 收件人公司
        industry: 行业
        product: 产品名称
        sender: 发件人姓名
        sender_company: 发件方公司
        budget: 预算（万元），用于 followup 邮件
        timeline: 实施周期

    Returns:
        SalesEmail
    """
    if email_type not in _TEMPLATES:
        email_type = "first_contact"

    template = _TEMPLATES[email_type]
    vars_ = {
        "name": _sanitize_field(to_name),
        "company": _sanitize_field(to_company),
        "industry": _sanitize_field(industry),
        "product": _sanitize_field(product, 50),
        "sender": _sanitize_field(sender),
        "sender_company": _sanitize_field(sender_company),
        "budget": str(budget) if budget else "合理",
        "timeline": _sanitize_field(timeline, 30),
        "date": str(date.today()),
    }

    subject = template["subject"].format(**vars_)
    body = template["body"].format(**vars_)

    # 截断正文
    from config import EMAIL_MAX_LENGTH
    if len(body) > EMAIL_MAX_LENGTH:
        body = body[:EMAIL_MAX_LENGTH - 3] + "..."

    return SalesEmail(
        to_name=to_name,
        to_company=to_company,
        subject=subject,
        body=body,
        email_type=email_type,
    )
