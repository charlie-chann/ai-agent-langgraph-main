# api.py — FastAPI for openclaw 微博内容 Agent
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run_generate_post, run_generate_batch, run_optimize_tags, run_plan_schedule, stream_chat

app = FastAPI(title="openclaw 微博 Agent API", version="1.0")


class GenerateRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None
    tone: str = "conversational"


class BatchRequest(BaseModel):
    topic: str
    count: int = 3


class TagRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    posts: list[str]


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "platform": "weibo"}


@app.post("/generate")
def generate(req: GenerateRequest):
    """生成单条微博。"""
    logger.info(f"POST /generate | topic={req.topic}")
    return run_generate_post(req.topic, req.keywords, req.tone)


@app.post("/generate/batch")
def generate_batch(req: BatchRequest):
    """批量生成微博。"""
    return run_generate_batch(req.topic, req.count)


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
