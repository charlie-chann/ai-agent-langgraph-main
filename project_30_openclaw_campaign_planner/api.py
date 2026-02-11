"""Project 30 - 营销活动规划 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import (
    run_plan_campaign, run_get_platform_schedule, run_get_phase_tasks,
    run_estimate_reach, run_list_campaign_types, stream_chat
)
from config import DEFAULT_MODEL, CAMPAIGN_TYPES, TARGET_PLATFORMS, MAX_CAMPAIGN_DAYS, MIN_CAMPAIGN_DAYS

app = FastAPI(
    title="📣 OpenClaw 营销活动规划 Agent API",
    description="跨平台营销日历自动生成与触达量预估服务",
    version="1.0.0"
)


class CampaignRequest(BaseModel):
    campaign_name: str = Field(..., description="活动名称")
    campaign_type: str = Field("brand_awareness", description=f"活动类型: {CAMPAIGN_TYPES}")
    start_date: str | None = Field(None, description="开始日期 YYYY-MM-DD，默认今天")
    duration_days: int = Field(30, ge=MIN_CAMPAIGN_DAYS, le=MAX_CAMPAIGN_DAYS, description="活动周期（天）")
    platforms: list[str] | None = Field(None, description=f"目标平台，默认前3个")
    budget: float = Field(10000.0, ge=0, description="预算（元）")
    topic: str = Field("", description="核心话题/关键词")


@app.get("/", summary="健康检查")
async def health():
    return {
        "status": "ok",
        "project": "campaign_planner",
        "model": DEFAULT_MODEL,
        "supported_types": CAMPAIGN_TYPES,
        "supported_platforms": TARGET_PLATFORMS
    }


@app.get("/campaign/types", summary="列出活动类型")
async def campaign_types():
    return {"types": run_list_campaign_types()}


@app.post("/campaign/plan", summary="生成营销活动计划")
async def plan_campaign(req: CampaignRequest):
    result = run_plan_campaign(
        campaign_name=req.campaign_name,
        campaign_type=req.campaign_type,
        start_date=req.start_date,
        duration_days=req.duration_days,
        platforms=req.platforms,
        budget=req.budget,
        topic=req.topic
    )
    if not result["success"]:
        return {"success": False, "error": result.get("error")}

    plan = result["plan"]
    return {
        "success": True,
        "campaign_name": plan.campaign_name,
        "campaign_type": plan.campaign_type,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "total_content_pieces": plan.total_content_pieces,
        "kpis": plan.kpis,
        "content": result["content"],
        "error": None
    }


@app.post("/campaign/plan/schedule", summary="获取平台发布日程")
async def platform_schedule(campaign_type: str = "brand_awareness",
                            campaign_name: str = "测试活动",
                            platform: str = Query(..., description="目标平台"),
                            duration_days: int = 30):
    result = run_plan_campaign(
        campaign_name=campaign_name,
        campaign_type=campaign_type,
        duration_days=duration_days,
        platforms=[platform]
    )
    if not result["success"]:
        return {"success": False, "error": result.get("error")}
    tasks = run_get_platform_schedule(result["plan"], platform)
    return {
        "platform": platform,
        "tasks": [
            {"date": t.scheduled_date, "content_type": t.content_type,
             "title": t.title, "phase": t.phase, "priority": t.priority}
            for t in tasks
        ],
        "count": len(tasks)
    }


@app.post("/campaign/reach", summary="估算触达量")
async def estimate_reach(req: CampaignRequest):
    result = run_plan_campaign(
        campaign_name=req.campaign_name,
        campaign_type=req.campaign_type,
        duration_days=req.duration_days,
        platforms=req.platforms,
        budget=req.budget,
        topic=req.topic
    )
    if not result["success"]:
        return {"success": False, "error": result.get("error")}
    reach = run_estimate_reach(result["plan"])
    return {"success": True, **reach}


@app.get("/chat/stream", summary="流式对话 (SSE)")
async def chat_stream(message: str = Query(..., description="用户消息")):
    def event_generator():
        try:
            for chunk in stream_chat(message):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8030)
