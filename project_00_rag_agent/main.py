"""
main.py — ASGI 入口：创建 FastAPI、挂中间件、include_router。

启动：uvicorn main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.v1 import router as v1_router
from app.gateway.rate_limit import rate_limit_middleware
from app.services.warmup_service import startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时预热，关闭时交由上下文管理器收尾。"""
    startup()
    yield


def create_app() -> FastAPI:
    """创建 FastAPI 应用：挂中间件、异常处理与 v1 路由。"""
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
