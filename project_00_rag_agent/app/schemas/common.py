"""通用请求/响应 Schema。"""
from __future__ import annotations

from pydantic import BaseModel


class TokenRequest(BaseModel):
    username: str
    password: str


class ErrorBody(BaseModel):
    error: str
    message: str
    request_id: str | None = None
