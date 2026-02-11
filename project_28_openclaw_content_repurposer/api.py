"""Project 28 - 内容改写 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import run_repurpose, run_repurpose_single, run_get_platform_specs, run_compliance_check, stream_chat
from config import DEFAULT_MODEL, SUPPORTED_PLATFORMS

app = FastAPI(
    title="✍️ OpenClaw 内容改写 Agent API",
    description="多平台内容一键适配与合规检查服务",
    version="1.0.0"
)


class RepurposeRequest(BaseModel):
    content: str = Field(..., description="原始内容")
    topic: str = Field("", description="话题/关键词")
    platforms: list[str] | None = Field(None, description="目标平台列表，为空时适配所有平台")


class RepurposeSingleRequest(BaseModel):
    content: str = Field(..., description="原始内容")
    topic: str = Field("", description="话题/关键词")
    platform: str = Field(..., description="目标平台")


class ComplianceRequest(BaseModel):
    content: str = Field(..., description="待检查内容")
    platform: str = Field(..., description="目标平台")


@app.get("/", summary="健康检查")
async def health():
    return {"status": "ok", "project": "content_repurposer", "model": DEFAULT_MODEL,
            "supported_platforms": SUPPORTED_PLATFORMS}


@app.post("/content/repurpose", summary="一键改写到多平台")
async def repurpose(req: RepurposeRequest):
    result = run_repurpose(
        content=req.content,
        topic=req.topic,
        target_platforms=req.platforms
    )
    return result


@app.post("/content/repurpose/{platform}", summary="改写到指定平台")
async def repurpose_single(platform: str, req: RepurposeSingleRequest):
    result = run_repurpose_single(
        content=req.content,
        topic=req.topic,
        platform=platform
    )
    return result


@app.get("/platform/specs", summary="获取平台规格")
async def platform_specs(platform: str | None = Query(None, description="平台名称，为空返回所有")):
    result = run_get_platform_specs(platform)
    return result


@app.post("/compliance/check", summary="内容合规检查")
async def compliance_check(req: ComplianceRequest):
    result = run_compliance_check(content=req.content, platform=req.platform)
    return result


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
    uvicorn.run(app, host="0.0.0.0", port=8028)
