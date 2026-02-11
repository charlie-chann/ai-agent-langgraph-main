"""领域异常 → HTTP 响应。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.exceptions import RAGError
from app.gateway.request_context import get_request_id
from app.infrastructure.observability.metrics import inc


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RAGError)
    async def rag_error_handler(_, exc: RAGError):
        inc("errors_total")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "request_id": get_request_id()},
        )
