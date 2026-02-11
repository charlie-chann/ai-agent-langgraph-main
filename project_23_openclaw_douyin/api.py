# api.py — FastAPI for openclaw 抖音脚本 Agent
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run_generate_script, run_optimize_tags, run_plan_schedule, stream_chat

app = FastAPI(title="openclaw 抖音 Agent API", version="1.0")


class ScriptRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None
    duration: int = 60           # 15 | 30 | 60 | 180
    style: str = "educational"   # educational | entertaining | motivational


class TagRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    posts: list[str]


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "platform": "douyin"}


@app.post("/generate/script")
def generate_script(req: ScriptRequest):
    """生成抖音视频脚本。"""
    logger.info(f"POST /generate/script | topic={req.topic} | duration={req.duration}s")
    return run_generate_script(req.topic, req.keywords, req.duration, req.style)


@app.post("/tags")
def optimize_tags(req: TagRequest):
    """优化话题标签。"""
    return run_optimize_tags(req.topic, req.keywords)


@app.post("/schedule")
def schedule(req: ScheduleRequest):
    """生成发布时间计划。"""
    return run_plan_schedule(req.posts)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """流式 AI 对话（SSE）。"""
    def _gen():
        for chunk in stream_chat(req.message):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")
