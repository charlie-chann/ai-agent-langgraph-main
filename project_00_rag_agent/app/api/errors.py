"""领域异常 → HTTP 响应。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.exceptions import AgentError
from app.gateway.request_context import get_request_id
from app.infrastructure.observability.metrics import inc


def register_exception_handlers(app: FastAPI) -> None:
    """注册领域异常到 HTTP JSON 响应的全局处理器。"""

    @app.exception_handler(AgentError)
    async def agent_error_handler(_, exc: AgentError):
        """将 AgentError 转为带 request_id 的 JSON 错误响应。"""
        inc("errors_total")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "request_id": get_request_id()},
        )
