"""营销活动日历生成器"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    MAX_CAMPAIGN_DAYS, MIN_CAMPAIGN_DAYS, MAX_CONTENT_PIECES_PER_DAY,
    MAX_TOTAL_CONTENT, CAMPAIGN_TYPES, TARGET_PLATFORMS,
    CONTENT_TYPES, CAMPAIGN_PHASES
)


@dataclass
class ContentTask:
    """营销内容任务"""
    day: int
    platform: str
    content_type: str
    phase: str
    topic: str
    description: str
    priority: Literal["high", "medium", "low"]
    estimated_reach: int
    deadline: str


@dataclass
class CampaignPlan:
    """完整营销活动计划"""
    campaign_name: str
    campaign_type: str
    start_date: str
    end_date: str
    duration_days: int
    target_platforms: list[str]
    phases: list[dict]
    content_calendar: list[ContentTask]
    budget_allocation: dict[str, float]
    total_content_pieces: int
    kpis: list[str]
    generated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def _calculate_phases(duration_days: int) -> list[dict]:
    """根据活动时长计算各阶段时间段"""
    phases = []
    # 预热: 20%, 爆发: 30%, 持续: 40%, 收尾: 10%
    weights = [0.20, 0.30, 0.40, 0.10]
    start = 1
    for phase_name, weight in zip(CAMPAIGN_PHASES, weights):
        days = max(1, int(duration_days * weight))
        phases.append({
            "name": phase_name,
            "start_day": start,
            "end_day": start + days - 1,
            "days": days
        })
        start += days
    # 调整最后阶段到实际结束
    if phases:
        phases[-1]["end_day"] = duration_days
        phases[-1]["days"] = duration_days - phases[-1]["start_day"] + 1
    return phases


def _get_phase_for_day(day: int, phases: list[dict]) -> str:
    for phase in phases:
        if phase["start_day"] <= day <= phase["end_day"]:
            return phase["name"]
    return "持续"


def _get_content_type_for_platform(platform: str) -> str:
    for content_type, platforms in CONTENT_TYPES.items():
        if platform in platforms:
            return content_type
    return "short_post"


def _estimate_reach(platform: str, phase: str) -> int:
    """估算发布内容的预期触达量"""
    base_reach = {
        "微博": 5000, "小红书": 3000, "知乎": 2000,
        "抖音": 8000, "Twitter": 1500, "微信公众号": 4000
    }
    phase_multiplier = {"预热": 0.6, "爆发": 1.5, "持续": 1.0, "收尾": 0.8}
    base = base_reach.get(platform, 2000)
    mult = phase_multiplier.get(phase, 1.0)
    return int(base * mult)


def generate_campaign_calendar(
    campaign_name: str,
    campaign_type: str,
    start_date: str,
    duration_days: int,
    platforms: list[str],
    budget: float = 10000.0,
    topic: str = ""
) -> CampaignPlan:
    """生成完整的营销活动日历"""
    from config import DEFAULT_BUDGET_ALLOCATION

    # 验证参数
    duration_days = max(MIN_CAMPAIGN_DAYS, min(MAX_CAMPAIGN_DAYS, duration_days))
    if campaign_type not in CAMPAIGN_TYPES:
        campaign_type = "brand_awareness"
    platforms = [p for p in platforms if p in TARGET_PLATFORMS] or TARGET_PLATFORMS[:3]

    # 计算结束日期
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        start_dt = datetime.now()
    end_dt = start_dt + timedelta(days=duration_days - 1)
    end_date = end_dt.strftime("%Y-%m-%d")

    phases = _calculate_phases(duration_days)

    # 生成内容日历
    content_tasks: list[ContentTask] = []
    daily_posts_per_platform = max(1, MAX_CONTENT_PIECES_PER_DAY // len(platforms))
    max_per_platform = MAX_TOTAL_CONTENT // len(platforms)
    platform_post_counts = {p: 0 for p in platforms}

    for day in range(1, duration_days + 1):
        phase = _get_phase_for_day(day, phases)
        current_date = (start_dt + timedelta(days=day - 1)).strftime("%Y-%m-%d")

        # 根据阶段决定发布频率
        post_multiplier = {"预热": 0.5, "爆发": 1.5, "持续": 1.0, "收尾": 0.5}
        posts_today = max(1, int(daily_posts_per_platform * post_multiplier.get(phase, 1.0)))

        for platform in platforms:
            if platform_post_counts[platform] >= max_per_platform:
                continue
            for _ in range(min(posts_today, 2)):
                if len(content_tasks) >= MAX_TOTAL_CONTENT:
                    break
                content_type = _get_content_type_for_platform(platform)
                priority = "high" if phase == "爆发" else "medium" if phase == "持续" else "low"
                reach = _estimate_reach(platform, phase)
                task_topic = topic if topic else campaign_name
                content_tasks.append(ContentTask(
                    day=day,
                    platform=platform,
                    content_type=content_type,
                    phase=phase,
                    topic=task_topic,
                    description=f"[{phase}期] 在{platform}发布{content_type}内容，主题：{task_topic[:20]}",
                    priority=priority,
                    estimated_reach=reach,
                    deadline=current_date
                ))
                platform_post_counts[platform] += 1

    # 预算分配
    budget_alloc = {}
    for platform in platforms:
        ratio = DEFAULT_BUDGET_ALLOCATION.get(platform, 1.0 / len(platforms))
        total_ratio = sum(DEFAULT_BUDGET_ALLOCATION.get(p, 1.0 / len(platforms)) for p in platforms)
        budget_alloc[platform] = round(budget * ratio / total_ratio, 2)

    # KPIs
    kpis = [
        f"总触达量目标: {sum(t.estimated_reach for t in content_tasks):,}",
        f"内容发布量: {len(content_tasks)} 条",
        f"预算利用率: ≥90%",
        f"品牌提及量增长: ≥30%",
        f"用户互动率: ≥5%"
    ]

    return CampaignPlan(
        campaign_name=campaign_name,
        campaign_type=campaign_type,
        start_date=start_date,
        end_date=end_date,
        duration_days=duration_days,
        target_platforms=platforms,
        phases=phases,
        content_calendar=content_tasks,
        budget_allocation=budget_alloc,
        total_content_pieces=len(content_tasks),
        kpis=kpis
    )


def format_campaign_markdown(plan: CampaignPlan) -> str:
    """将营销计划格式化为 Markdown"""
    lines = [
        f"# 📅 营销活动规划：{plan.campaign_name}",
        f"> 类型: {plan.campaign_type} | 时长: {plan.duration_days}天 ({plan.start_date} ~ {plan.end_date})",
        f"> 平台: {', '.join(plan.target_platforms)} | 内容量: {plan.total_content_pieces}条",
        "",
        "---",
        "",
        "## 📊 活动阶段",
        ""
    ]
    phase_emoji = {"预热": "🌱", "爆发": "🔥", "持续": "⚡", "收尾": "🌙"}
    for phase in plan.phases:
        emoji = phase_emoji.get(phase["name"], "📌")
        lines.append(f"- {emoji} **{phase['name']}** (Day {phase['start_day']} ~ Day {phase['end_day']}, {phase['days']}天)")

    lines += ["", "## 💡 关键KPI目标", ""]
    for kpi in plan.kpis:
        lines.append(f"- {kpi}")

    lines += ["", "## 💰 预算分配", ""]
    for platform, amount in plan.budget_allocation.items():
        lines.append(f"- {platform}: ¥{amount:,.2f}")

    lines += ["", "## 📋 内容发布日历（前10条）", ""]
    for task in plan.content_calendar[:10]:
        lines.append(
            f"- Day{task.day:02d} | {task.platform} | {task.phase} | "
            f"{task.content_type} | 预计触达: {task.estimated_reach:,}"
        )
    if len(plan.content_calendar) > 10:
        lines.append(f"\n…以及 {len(plan.content_calendar) - 10} 条更多内容任务")

    return "\n".join(lines)
