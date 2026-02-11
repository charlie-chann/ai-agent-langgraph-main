"""Project 25 - 早报 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import run_generate_brief, run_list_sources, stream_chat
from config import DEFAULT_MODEL, OLLAMA_BASE_URL

app = FastAPI(
    title="🌅 OpenClaw 早报 Agent API",
    description="基于 RSS 聚合的智能早报生成服务",
    version="1.0.0"
)


class BriefRequest(BaseModel):
    date: str | None = Field(None, description="日期 YYYY-MM-DD，默认今天")
    output_format: str = Field("markdown", description="输出格式: markdown | plain")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")


@app.get("/", summary="健康检查")
async def health():
    return {"status": "ok", "project": "morning_brief", "model": DEFAULT_MODEL}


@app.post("/brief/generate", summary="生成今日早报")
async def generate_brief(req: BriefRequest = BriefRequest()):
    result = run_generate_brief(date=req.date, output_format=req.output_format)
    if not result["success"]:
        return {"success": False, "error": result.get("error"), "content": ""}
    return {
        "success": True,
        "date": result["brief"].date if result["brief"] else req.date,
        "article_count": result["article_count"],
        "content": result["content"],
        "error": None
    }


@app.get("/sources/list", summary="列出所有 RSS 源")
async def list_sources():
    result = run_list_sources()
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
    uvicorn.run(app, host="0.0.0.0", port=8025)
