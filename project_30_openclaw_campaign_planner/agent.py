"""营销活动规划 Agent - 核心业务逻辑"""

import re
from pathlib import Path
from datetime import datetime
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    CAMPAIGN_TYPES, TARGET_PLATFORMS, MAX_CAMPAIGN_DAYS, MIN_CAMPAIGN_DAYS
)
from tools.campaign_calendar import (
    generate_campaign_calendar, format_campaign_markdown,
    CampaignPlan, ContentTask
)


def _sanitize_input(text: str) -> str:
    text = text.strip()
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:500]


def run_plan_campaign(
    campaign_name: str,
    campaign_type: str = "brand_awareness",
    start_date: str | None = None,
    duration_days: int = 30,
    platforms: list[str] | None = None,
    budget: float = 10000.0,
    topic: str = ""
) -> dict:
    """
    生成完整营销活动计划。
    
    Returns: {
        success, plan, content, total_content, kpis, error
    }
    """
    campaign_name = _sanitize_input(campaign_name)
    topic = _sanitize_input(topic)

    if not campaign_name:
        return {"success": False, "error": "活动名称不能为空", "plan": None}

    if duration_days < MIN_CAMPAIGN_DAYS or duration_days > MAX_CAMPAIGN_DAYS:
        duration_days = max(MIN_CAMPAIGN_DAYS, min(MAX_CAMPAIGN_DAYS, duration_days))

    if start_date is None:
        start_date = datetime.now().strftime("%Y-%m-%d")

    platforms = platforms or TARGET_PLATFORMS[:3]

    try:
        plan = generate_campaign_calendar(
            campaign_name=campaign_name,
            campaign_type=campaign_type,
            start_date=start_date,
            duration_days=duration_days,
            platforms=platforms,
            budget=budget,
            topic=topic
        )
        content = format_campaign_markdown(plan)
        return {
            "success": True,
            "plan": plan,
            "content": content,
            "total_content": plan.total_content_pieces,
            "kpis": plan.kpis,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e), "plan": None}


def run_get_platform_schedule(plan: CampaignPlan, platform: str) -> list[ContentTask]:
    """获取特定平台的内容发布计划"""
    return [task for task in plan.content_calendar if task.platform == platform]


def run_get_phase_tasks(plan: CampaignPlan, phase: str) -> list[ContentTask]:
    """获取特定阶段的任务列表"""
    return [task for task in plan.content_calendar if task.phase == phase]


def run_estimate_reach(plan: CampaignPlan) -> dict:
    """估算总触达量"""
    by_platform: dict[str, int] = {}
    by_phase: dict[str, int] = {}
    total = 0
    for task in plan.content_calendar:
        by_platform[task.platform] = by_platform.get(task.platform, 0) + task.estimated_reach
        by_phase[task.phase] = by_phase.get(task.phase, 0) + task.estimated_reach
        total += task.estimated_reach
    return {
        "total_estimated_reach": total,
        "by_platform": by_platform,
        "by_phase": by_phase
    }


def run_list_campaign_types() -> list[str]:
    return CAMPAIGN_TYPES


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与营销规划 Agent 的流式对话"""
    from langchain_community.chat_models import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage

    user_input = _sanitize_input(user_input[:500])
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE
    )
    messages = [
        SystemMessage(content=(
            "你是一位经验丰富的数字营销专家，擅长制定多平台营销活动策略。"
            "你熟悉微博、小红书、知乎、抖音、Twitter等平台的内容策略，"
            "能够为品牌提供专业的营销活动规划建议。"
        )),
        HumanMessage(content=user_input)
    ]
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
