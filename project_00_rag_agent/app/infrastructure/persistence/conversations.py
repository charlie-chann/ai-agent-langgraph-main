"""
storage/conversations.py — 会话与消息持久化

【职责】
1. conversations / messages 表：按 user_id + conversation_id 管理多轮聊天
2. PostgreSQL 为主（与 Checkpointer 共用 DATABASE_URL）；不可用时降级 SQLite

【设计原因】
1. 生产形态：客户端只发 conversation_id + message，历史由服务端加载
2. conversation_id 同时作为 LangGraph thread_id，HITL 续跑与聊天记录对齐
3. SQLite 降级：本地单测 / 无 Postgres 时仍可运行 API
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterator, List, Optional

from loguru import logger

from app.core.config import PROJECT_ROOT, settings

_store: Optional["ConversationStore"] = None
_store_lock = Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConversationStore(ABC):
  @abstractmethod
  def setup(self) -> None: ...

  @abstractmethod
  def create_conversation(self, user_id: str, title: Optional[str] = None) -> dict: ...

  @abstractmethod
  def get_conversation(self, conversation_id: str, user_id: str) -> Optional[dict]: ...

  @abstractmethod
  def list_conversations(self, user_id: str, *, limit: int = 50) -> List[dict]: ...

  @abstractmethod
  def list_messages(self, conversation_id: str) -> List[dict]: ...

  @abstractmethod
  def append_message(
      self,
      conversation_id: str,
      role: str,
      content: str,
      *,
      metadata: Optional[dict] = None,
  ) -> dict: ...

  @abstractmethod
  def touch_conversation(self, conversation_id: str, *, title: Optional[str] = None) -> None: ...

  @abstractmethod
  def backend_name(self) -> str: ...


class PostgresConversationStore(ConversationStore):
  def __init__(self, database_url: str):
    import psycopg

    self._database_url = database_url
    self._psycopg = psycopg

  @contextmanager
  def _conn(self):
    with self._psycopg.connect(self._database_url) as conn:
      yield conn

  def setup(self) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
    """
    with self._conn() as conn:
      conn.execute(ddl)
      conn.commit()
    logger.info("Conversation store: PostgreSQL tables ready")

  def create_conversation(self, user_id: str, title: Optional[str] = None) -> dict:
    conv_id = str(uuid.uuid4())
    now = _utc_now()
    with self._conn() as conn:
      conn.execute(
          """
          INSERT INTO conversations (id, user_id, title, created_at, updated_at)
          VALUES (%s, %s, %s, %s, %s)
          """,
          (conv_id, user_id, title, now, now),
      )
      conn.commit()
    return {
        "conversation_id": conv_id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }

  def get_conversation(self, conversation_id: str, user_id: str) -> Optional[dict]:
    with self._conn() as conn:
      row = conn.execute(
          """
          SELECT id::text, user_id, title, created_at, updated_at
          FROM conversations
          WHERE id = %s AND user_id = %s
          """,
          (conversation_id, user_id),
      ).fetchone()
    if not row:
      return None
    return {
        "conversation_id": row[0],
        "user_id": row[1],
        "title": row[2],
        "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        "updated_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
    }

  def list_conversations(self, user_id: str, *, limit: int = 50) -> List[dict]:
    with self._conn() as conn:
      rows = conn.execute(
          """
          SELECT c.id::text, c.title, c.created_at, c.updated_at,
                 COUNT(m.id) AS message_count
          FROM conversations c
          LEFT JOIN messages m ON m.conversation_id = c.id
          WHERE c.user_id = %s
          GROUP BY c.id, c.title, c.created_at, c.updated_at
          ORDER BY c.updated_at DESC
          LIMIT %s
          """,
          (user_id, limit),
      ).fetchall()
    out = []
    for row in rows:
      out.append({
          "conversation_id": row[0],
          "title": row[1],
          "created_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
          "updated_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
          "message_count": int(row[4]),
      })
    return out

  def list_messages(self, conversation_id: str) -> List[dict]:
    with self._conn() as conn:
      rows = conn.execute(
          """
          SELECT role, content, metadata, created_at
          FROM messages
          WHERE conversation_id = %s
          ORDER BY id ASC
          """,
          (conversation_id,),
      ).fetchall()
    return [
        {
            "role": row[0],
            "content": row[1],
            "metadata": row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}"),
            "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }
        for row in rows
    ]

  def append_message(
      self,
      conversation_id: str,
      role: str,
      content: str,
      *,
      metadata: Optional[dict] = None,
  ) -> dict:
    meta = metadata or {}
    now = _utc_now()
    with self._conn() as conn:
      row = conn.execute(
          """
          INSERT INTO messages (conversation_id, role, content, metadata, created_at)
          VALUES (%s, %s, %s, %s::jsonb, %s)
          RETURNING id, created_at
          """,
          (conversation_id, role, content, json.dumps(meta, ensure_ascii=False), now),
      ).fetchone()
      conn.execute(
          "UPDATE conversations SET updated_at = %s WHERE id = %s",
          (now, conversation_id),
      )
      conn.commit()
    return {
        "role": role,
        "content": content,
        "metadata": meta,
        "created_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1]),
    }

  def touch_conversation(self, conversation_id: str, *, title: Optional[str] = None) -> None:
    with self._conn() as conn:
      if title is not None:
        conn.execute(
            "UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s",
            (title, _utc_now(), conversation_id),
        )
      else:
        conn.execute(
            "UPDATE conversations SET updated_at = %s WHERE id = %s",
            (_utc_now(), conversation_id),
        )
      conn.commit()

  def backend_name(self) -> str:
    return "postgres"


class SqliteConversationStore(ConversationStore):
  def __init__(self, db_path: Path):
    self._db_path = db_path
    self._db_path.parent.mkdir(parents=True, exist_ok=True)
    self._lock = Lock()

  @contextmanager
  def _conn(self) -> Iterator[sqlite3.Connection]:
    with self._lock:
      conn = sqlite3.connect(self._db_path)
      conn.row_factory = sqlite3.Row
      conn.execute("PRAGMA foreign_keys = ON")
      try:
        yield conn
        conn.commit()
      finally:
        conn.close()

  def setup(self) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
        content TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
    """
    with self._conn() as conn:
      conn.executescript(ddl)
    logger.info(f"Conversation store: SQLite ready at {self._db_path}")

  def create_conversation(self, user_id: str, title: Optional[str] = None) -> dict:
    conv_id = str(uuid.uuid4())
    now = _utc_now()
    with self._conn() as conn:
      conn.execute(
          """
          INSERT INTO conversations (id, user_id, title, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?)
          """,
          (conv_id, user_id, title, now, now),
      )
    return {
        "conversation_id": conv_id,
        "user_id": user_id,
        "title": title,
        "created_at": now,
        "updated_at": now,
    }

  def get_conversation(self, conversation_id: str, user_id: str) -> Optional[dict]:
    with self._conn() as conn:
      row = conn.execute(
          "SELECT id, user_id, title, created_at, updated_at FROM conversations WHERE id = ? AND user_id = ?",
          (conversation_id, user_id),
      ).fetchone()
    if not row:
      return None
    return dict(row) | {"conversation_id": row["id"]}

  def list_conversations(self, user_id: str, *, limit: int = 50) -> List[dict]:
    with self._conn() as conn:
      rows = conn.execute(
          """
          SELECT c.id AS conversation_id, c.title, c.created_at, c.updated_at,
                 COUNT(m.id) AS message_count
          FROM conversations c
          LEFT JOIN messages m ON m.conversation_id = c.id
          WHERE c.user_id = ?
          GROUP BY c.id, c.title, c.created_at, c.updated_at
          ORDER BY c.updated_at DESC
          LIMIT ?
          """,
          (user_id, limit),
      ).fetchall()
    return [dict(row) for row in rows]

  def list_messages(self, conversation_id: str) -> List[dict]:
    with self._conn() as conn:
      rows = conn.execute(
          """
          SELECT role, content, metadata, created_at
          FROM messages
          WHERE conversation_id = ?
          ORDER BY id ASC
          """,
          (conversation_id,),
      ).fetchall()
    out = []
    for row in rows:
      out.append({
          "role": row["role"],
          "content": row["content"],
          "metadata": json.loads(row["metadata"] or "{}"),
          "created_at": row["created_at"],
      })
    return out

  def append_message(
      self,
      conversation_id: str,
      role: str,
      content: str,
      *,
      metadata: Optional[dict] = None,
  ) -> dict:
    meta = metadata or {}
    now = _utc_now()
    with self._conn() as conn:
      conn.execute(
          """
          INSERT INTO messages (conversation_id, role, content, metadata, created_at)
          VALUES (?, ?, ?, ?, ?)
          """,
          (conversation_id, role, content, json.dumps(meta, ensure_ascii=False), now),
      )
      conn.execute(
          "UPDATE conversations SET updated_at = ? WHERE id = ?",
          (now, conversation_id),
      )
    return {"role": role, "content": content, "metadata": meta, "created_at": now}

  def touch_conversation(self, conversation_id: str, *, title: Optional[str] = None) -> None:
    with self._conn() as conn:
      if title is not None:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, _utc_now(), conversation_id),
        )
      else:
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_utc_now(), conversation_id),
        )

  def backend_name(self) -> str:
    return "sqlite"


def _build_store() -> ConversationStore:
  backend = settings.conversations_backend
  if backend == "sqlite":
    store = SqliteConversationStore(settings.conversations_sqlite_path)
    store.setup()
    return store

  if backend == "postgres":
    store = PostgresConversationStore(settings.database_url)
    store.setup()
    return store

  # auto: try postgres, fallback sqlite
  try:
    store = PostgresConversationStore(settings.database_url)
    store.setup()
    return store
  except Exception as e:
    logger.warning(f"PostgreSQL conversation store unavailable, using SQLite: {e}")
    sqlite_store = SqliteConversationStore(settings.conversations_sqlite_path)
    sqlite_store.setup()
    return sqlite_store


def get_conversation_store() -> ConversationStore:
  global _store
  if _store is None:
    with _store_lock:
      if _store is None:
        _store = _build_store()
  return _store


def messages_as_chat_history(messages: List[dict]) -> List[dict]:
    """DB messages → API/compression 可用的 {role, content} 列表。"""
    return [{"role": m["role"], "content": m["content"]} for m in messages]


def reset_conversation_store() -> None:
  """测试隔离：重置 store 单例。"""
  global _store
  with _store_lock:
    _store = None
