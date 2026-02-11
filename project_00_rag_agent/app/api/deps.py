"""公共 FastAPI 依赖：鉴权、会话存储等。"""
from __future__ import annotations

from app.gateway.auth import TokenPayload, require_permission
from app.infrastructure.persistence.conversations import get_conversation_store

__all__ = [
    "TokenPayload",
    "require_permission",
    "get_conversation_store",
]
