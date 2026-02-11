# api.py — FastAPI for openclaw 知乎内容 Agent
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run_generate_answer, run_optimize_tags, run_plan_schedule, stream_chat

app = FastAPI(title="openclaw 知乎 Agent API", version="1.0")


class AnswerRequest(BaseModel):
    question: str
    topic: str = "科技"
    expertise_level: str = "intermediate"  # beginner | intermediate | expert


class TagRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    posts: list[str]


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "platform": "zhihu"}


@app.post("/generate/answer")
def generate_answer(req: AnswerRequest):
    """生成知乎回答。"""
    logger.info(f"POST /generate/answer | question={req.question[:30]}")
    return run_generate_answer(req.question, req.topic, req.expertise_level)


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
