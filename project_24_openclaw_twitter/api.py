# api.py — FastAPI for openclaw Twitter/X Agent
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run_generate_tweet, run_generate_thread, run_optimize_tags, run_plan_schedule, stream_chat

app = FastAPI(title="openclaw Twitter Agent API", version="1.0")


class TweetRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None
    style: str = "informative"   # informative | engaging | promotional | thread_hook


class ThreadRequest(BaseModel):
    topic: str
    points: Optional[list[str]] = None
    num_tweets: int = 5


class TagRequest(BaseModel):
    topic: str
    keywords: Optional[list[str]] = None


class ScheduleRequest(BaseModel):
    posts: list[str]


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"status": "ok", "platform": "twitter"}


@app.post("/generate/tweet")
def generate_tweet(req: TweetRequest):
    """Generate a single tweet (≤280 chars)."""
    logger.info(f"POST /generate/tweet | topic={req.topic}")
    return run_generate_tweet(req.topic, req.keywords, req.style)


@app.post("/generate/thread")
def generate_thread(req: ThreadRequest):
    """Generate a Twitter thread."""
    logger.info(f"POST /generate/thread | topic={req.topic} | tweets={req.num_tweets}")
    return run_generate_thread(req.topic, req.points, req.num_tweets)


@app.post("/tags")
def optimize_tags(req: TagRequest):
    """Optimize hashtags (max 3 for Twitter)."""
    return run_optimize_tags(req.topic, req.keywords)


@app.post("/schedule")
def schedule(req: ScheduleRequest):
    """Generate UTC posting schedule."""
    return run_plan_schedule(req.posts)


@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    """Streaming AI chat (SSE)."""
    def _gen():
        for chunk in stream_chat(req.message):
            yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")
