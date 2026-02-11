"""storage 包 — 会话与消息持久化（PostgreSQL 主存储，SQLite 降级）。"""

from app.infrastructure.persistence.conversations import get_conversation_store

__all__ = ["get_conversation_store"]
