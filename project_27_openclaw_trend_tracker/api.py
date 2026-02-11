"""Project 27 - 热点追踪 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import run_track_topic, run_batch_track, run_get_trending, stream_chat
from config import DEFAULT_MODEL

DEFAULT_TOPICS = ["AI科技", "伊朗局势", "中国经济"]

app = FastAPI(
    title="🔥 OpenClaw 热点追踪 Agent API",
    description="多平台热点话题监控与内容机会分析服务",
    version="1.0.0"
)


class TrackRequest(BaseModel):
    topic: str = Field(..., description="追踪话题")
    keywords: list[str] | None = Field(None, description="附加关键词")


class BatchTrackRequest(BaseModel):
    topics: list[str] | None = Field(None, description="话题列表，为空时使用默认话题")


@app.get("/", summary="健康检查")
async def health():
    return {"status": "ok", "project": "trend_tracker", "model": DEFAULT_MODEL,
            "default_topics": DEFAULT_TOPICS}


@app.post("/trend/track", summary="追踪单个话题热度")
async def track_topic(req: TrackRequest):
    result = run_track_topic(topic=req.topic, keywords=req.keywords)
    return result


@app.post("/trend/batch", summary="批量追踪多个话题")
async def batch_track(req: BatchTrackRequest = BatchTrackRequest()):
    results = run_batch_track(topics=req.topics)
    return {"topics": results, "count": len(results)}


@app.get("/trending", summary="获取当前最热话题排行")
async def get_trending(top_n: int = Query(5, ge=1, le=20, description="返回前 N 个话题")):
    results = run_get_trending(top_n=top_n)
    return {"trending": results, "count": len(results)}


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
    uvicorn.run(app, host="0.0.0.0", port=8027)
