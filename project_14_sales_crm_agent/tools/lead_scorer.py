# tools/lead_scorer.py — 线索评分工具
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from config import LEAD_HOT_SCORE, LEAD_WARM_SCORE


# 行业权重（某些行业成交率更高）
_INDUSTRY_WEIGHTS: dict[str, int] = {
    "金融": 15, "医疗": 15, "制造": 12, "零售": 10,
    "教育": 8, "互联网": 12, "政府": 10, "科技": 12,
}

# 职位权重（决策层权重高）
_TITLE_WEIGHTS: dict[str, int] = {
    "CEO": 20, "CTO": 18, "CFO": 18, "总经理": 18, "总裁": 20,
    "副总": 15, "总监": 12, "经理": 8, "主任": 8, "采购": 10,
}


@dataclass
class Lead:
    """销售线索数据类。"""
    lead_id: str
    name: str
    company: str
    title: str
    industry: str
    budget: float           # 预算（万元）
    timeline_days: int      # 预计采购周期（天）
    engagement_score: int   # 互动活跃度 0-100（点击/回复/会面次数）
    last_contact_date: str  # 最近联系日期 YYYY-MM-DD
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "线索ID": self.lead_id,
            "姓名": self.name,
            "公司": self.company,
            "职位": self.title,
            "行业": self.industry,
            "预算(万)": self.budget,
            "采购周期(天)": self.timeline_days,
            "互动得分": self.engagement_score,
            "最近联系": self.last_contact_date,
            "备注": self.notes,
        }


@dataclass
class LeadScore:
    """线索评分结果。"""
    lead_id: str
    total_score: int
    grade: str              # "hot" | "warm" | "cold"
    score_breakdown: dict
    recommended_action: str
    next_followup_date: str

    def to_dict(self) -> dict:
        return {
            "线索ID": self.lead_id,
            "总分": self.total_score,
            "等级": self.grade,
            "分项得分": self.score_breakdown,
            "建议行动": self.recommended_action,
            "建议跟进日期": self.next_followup_date,
        }


def score_lead(lead: Lead) -> LeadScore:
    """
    对销售线索进行综合评分（0-100分）。

    评分维度：
    - 预算规模 (0-25分)
    - 决策层职位 (0-20分)
    - 行业匹配度 (0-15分)
    - 采购紧迫度 (0-20分)
    - 互动活跃度 (0-20分)
    """
    breakdown = {}

    # 1. 预算得分（≥100万→满分）
    if lead.budget >= 100:
        budget_score = 25
    elif lead.budget >= 50:
        budget_score = 20
    elif lead.budget >= 20:
        budget_score = 15
    elif lead.budget >= 5:
        budget_score = 8
    else:
        budget_score = 3
    breakdown["预算"] = budget_score

    # 2. 职位权重
    title_score = 0
    for kw, w in _TITLE_WEIGHTS.items():
        if kw in lead.title:
            title_score = w
            break
    breakdown["职位"] = title_score

    # 3. 行业匹配
    industry_score = _INDUSTRY_WEIGHTS.get(lead.industry, 5)
    breakdown["行业"] = industry_score

    # 4. 采购紧迫度（周期越短越紧迫）
    if lead.timeline_days <= 30:
        timeline_score = 20
    elif lead.timeline_days <= 90:
        timeline_score = 15
    elif lead.timeline_days <= 180:
        timeline_score = 10
    else:
        timeline_score = 3
    breakdown["紧迫度"] = timeline_score

    # 5. 互动活跃度（原始得分归一化到20分）
    engagement_score = min(20, int(lead.engagement_score / 5))
    breakdown["互动度"] = engagement_score

    total = sum(breakdown.values())
    total = min(total, 100)  # 上限100

    # 等级判断
    if total >= LEAD_HOT_SCORE:
        grade = "hot"
        action = "立即安排销售拜访或演示"
        days_until_followup = 1
    elif total >= LEAD_WARM_SCORE:
        grade = "warm"
        action = "发送个性化邮件，安排电话沟通"
        days_until_followup = 3
    else:
        grade = "cold"
        action = "加入培育序列，每周发送行业资讯"
        days_until_followup = 7

    next_date = str(date.today() + timedelta(days=days_until_followup))

    return LeadScore(
        lead_id=lead.lead_id,
        total_score=total,
        grade=grade,
        score_breakdown=breakdown,
        recommended_action=action,
        next_followup_date=next_date,
    )
