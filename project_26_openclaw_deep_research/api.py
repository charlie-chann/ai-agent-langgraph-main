"""Project 26 - 深度调研 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import run_research, run_validate_topic, stream_chat
from config import DEFAULT_MODEL, RESEARCH_DEPTHS as RESEARCH_DEPTH_LEVELS

app = FastAPI(
    title="🔬 OpenClaw 深度调研 Agent API",
    description="多维度深度研究报告生成服务",
    version="1.0.0"
)


class ResearchRequest(BaseModel):
    topic: str = Field(..., description="调研主题")
    depth: str = Field("standard", description=f"调研深度: {RESEARCH_DEPTH_LEVELS}")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")


@app.get("/", summary="健康检查")
async def health():
    return {"status": "ok", "project": "deep_research", "model": DEFAULT_MODEL}


@app.post("/research/run", summary="执行深度调研")
async def research(req: ResearchRequest):
    result = run_research(topic=req.topic, depth=req.depth)
    if not result["success"]:
        return {"success": False, "error": result.get("error")}
    return {
        "success": True,
        "topic": req.topic,
        "depth": req.depth,
        "confidence_score": result.get("confidence_score"),
        "word_count": result.get("word_count"),
        "content": result.get("content"),
        "error": None
    }


@app.post("/topic/validate", summary="验证调研话题可行性")
async def validate_topic(topic: str = Query(..., description="调研话题")):
    result = run_validate_topic(topic)
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
    uvicorn.run(app, host="0.0.0.0", port=8026)
