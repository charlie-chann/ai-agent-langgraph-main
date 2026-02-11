"""
main.py — ASGI 入口：创建 FastAPI、挂中间件、include_router。

启动：uvicorn main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1 import router as v1_router
from app.agent.graph.checkpointer import get_checkpointer
from app.gateway.rate_limit import rate_limit_middleware
from app.infrastructure.persistence.conversations import get_conversation_store
from app.services.warmup_service import warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    warmup()
    get_checkpointer()
    get_conversation_store().setup()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Production RAG Agent API",
        version="2.1.0",
        lifespan=lifespan,
    )
    application.middleware("http")(rate_limit_middleware)
    register_exception_handlers(application)
    # 保持原有 URL（/chat、/ingest…），不强制 /api/v1 前缀以免破坏客户端
    application.include_router(v1_router)
    return application


app = create_app()
