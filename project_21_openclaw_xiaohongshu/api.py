# api.py — openclaw 小红书内容 Agent FastAPI HTTP 服务
#
# 【接口】
#   GET  /health        → 健康检查
#   POST /generate      → 生成小红书笔记
#   POST /tags          → 优化话题标签
#   POST /schedule      → 生成发布排期
#   POST /chat/stream   → SSE 流式 AI 运营顾问对话
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run_generate_post, run_optimize_tags, run_plan_schedule, stream_chat

app = FastAPI(title="openclaw 小红书 Agent API", version="1.0")


# ── 请求体数据模型 ─────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    """笔记生成请求：话题 + 可选关键词 + 风格。"""
    topic: str
    keywords: Optional[list[str]] = None
    style: str = "lifestyle"  # lifestyle | tutorial | review


class TagRequest(BaseModel):
    """标签优化请求。"""
    topic: str
    keywords: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    """排期请求：待发布的笔记内容列表。"""
    posts: list[str]


class ChatRequest(BaseModel):
    """流式对话请求。"""
    message: str


# ── API 端点 ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """健康检查。"""
    return {"status": "ok", "platform": "xiaohongshu"}


@app.post("/generate")
def generate(req: GenerateRequest):
    """生成小红书图文笔记，返回标题/正文/标签/配图建议/合规检查。"""
    logger.info(f"POST /generate | topic={req.topic} | style={req.style}")
    return run_generate_post(req.topic, req.keywords, req.style)


@app.post("/tags")
def optimize_tags(req: TagRequest):
    """优化话题标签，返回推荐标签和预估互动得分。"""
    return run_optimize_tags(req.topic, req.keywords)


@app.post("/schedule")
def schedule(req: ScheduleRequest):
    """为多篇笔记生成发布时间计划表。"""
    return run_plan_schedule(req.posts)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """SSE 流式 AI 运营顾问对话，逐 token 推送。"""
    def _gen():
        for chunk in stream_chat(req.message):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")
