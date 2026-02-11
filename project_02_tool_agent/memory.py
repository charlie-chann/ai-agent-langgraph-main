"""
memory.py — 多轮对话记忆管理

【职责】
1. ConversationMemory：单会话的消息存储（user/ai/tool 三种角色）
2. MemoryStore：多 session 管理，支持并发、容量淘汰、历史截断
3. 提供 LangChain Message 格式转换，供 agent 直接注入上下文

【设计原因】
1. ReAct Agent 默认无记忆，多轮对话需自行维护 chat_history
2. 内存存储适合 demo；生产可替换为 Redis / DB，接口不变
3. 线程锁 RLock：Streamlit / FastAPI 并发请求时保证 session 安全
"""
from typing import List, Dict, Optional
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from dataclasses import dataclass, field
import json
import threading

from loguru import logger


@dataclass
class ConversationMemory:
    """单个会话的记忆容器，存储该 session 的全部消息。"""

    session_id: str
    messages: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)

    def add_user_message(self, content: str) -> None:
        """追加一条用户消息到历史。"""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_updated = datetime.now().isoformat()

    def add_ai_message(self, content: str) -> None:
        """追加一条 AI 回复到历史。"""
        self.messages.append({
            "role": "ai",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_updated = datetime.now().isoformat()

    def add_tool_call(self, tool_name: str, input_data: str, output: str) -> None:
        """追加一条工具调用记录（用于审计/展示，不注入 LangChain 上下文）。"""
        self.messages.append({
            "role": "tool",
            "tool_name": tool_name,
            "input": input_data,
            "output": output,
            "timestamp": datetime.now().isoformat(),
        })

    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """
        获取原始消息列表（dict 格式，供 UI/API 展示）。

        参数:
            limit: 只返回最近 N 条；None 表示全部
        """
        if limit is None:
            return self.messages.copy()
        return self.messages[-limit:] if limit > 0 else self.messages.copy()

    def get_langchain_messages(self, limit: Optional[int] = None) -> List[BaseMessage]:
        """
        转换为 LangChain HumanMessage / AIMessage 列表，供 agent.invoke 使用。

        说明:
            tool 类型消息会被跳过——工具调用细节由 ReAct scratchpad 管理。
        """
        history = self.get_messages(limit)
        result = []
        for msg in history:
            if msg["role"] == "user":
                result.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                result.append(AIMessage(content=msg["content"]))
        return result

    def clear(self) -> None:
        """清空本会话所有消息，保留 session_id。"""
        self.messages.clear()
        self.last_updated = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """序列化为 dict，便于持久化到 JSON / Redis。"""
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationMemory":
        """从 dict 反序列化，恢复会话对象。"""
        return cls(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class MemoryStore:
    """
    全局记忆仓库，管理多个 session_id 对应的 ConversationMemory。

    典型用法:
        store = get_memory_store()
        store.get_or_create_session("user123")
        store.get_langchain_messages("user123", limit=20)
    """

    def __init__(self, max_sessions: int = 1000, max_history_per_session: int = 100):
        """
        初始化存储。

        参数:
            max_sessions: 最多缓存多少个 session，超出则淘汰最久未更新的
            max_history_per_session: 每个 session 最多保留多少条消息
        """
        self._sessions: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()  # 可重入锁，同线程多次 acquire 不会死锁
        self._max_sessions = max_sessions
        self._max_history = max_history_per_session

    def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> ConversationMemory:
        """创建新会话；若已存在则直接返回现有会话。"""
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]

            # 容量满时，淘汰 last_updated 最早的 session（LRU 策略）
            if len(self._sessions) >= self._max_sessions:
                oldest = min(self._sessions.items(), key=lambda x: x[1].last_updated)
                del self._sessions[oldest[0]]
                logger.info(f"MemoryStore: Evicted oldest session {oldest[0]}")

            memory = ConversationMemory(
                session_id=session_id,
                metadata=metadata or {}
            )
            self._sessions[session_id] = memory
            logger.info(f"MemoryStore: Created session {session_id}")
            return memory

    def get_session(self, session_id: str) -> Optional[ConversationMemory]:
        """按 ID 获取会话，不存在返回 None。"""
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str, metadata: Optional[Dict] = None) -> ConversationMemory:
        """获取已有会话，不存在则创建。"""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id, metadata)
        return session

    def add_message(self, session_id: str, content: str, role: str) -> None:
        """
        向指定 session 追加消息。

        参数:
            role: "user" | "ai" | "tool"（tool 请用 add_tool_call）
        """
        with self._lock:
            session = self.get_or_create_session(session_id)

            if role == "user":
                session.add_user_message(content)
            elif role == "ai":
                session.add_ai_message(content)
            elif role == "tool":
                pass  # 工具调用请走 add_tool_call

            # 超出上限时保留最近 N 条，防止内存无限增长
            if len(session.messages) > self._max_history:
                session.messages = session.messages[-self._max_history:]

    def add_tool_call(self, session_id: str, tool_name: str, input_data: str, output: str) -> None:
        """记录一次工具调用到指定 session。"""
        with self._lock:
            session = self.get_or_create_session(session_id)
            session.add_tool_call(tool_name, input_data, output)

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """获取指定 session 的消息列表；session 不存在返回空列表。"""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get_messages(limit)

    def get_langchain_messages(self, session_id: str, limit: Optional[int] = None) -> List[BaseMessage]:
        """获取 LangChain 格式历史，供 agent 注入上下文。"""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get_langchain_messages(limit)

    def clear_session(self, session_id: str) -> None:
        """清空指定 session 的消息，不删除 session 本身。"""
        with self._lock:
            session = self.get_session(session_id)
            if session:
                session.clear()
                logger.info(f"MemoryStore: Cleared session {session_id}")

    def delete_session(self, session_id: str) -> None:
        """彻底删除 session 及其全部数据。"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"MemoryStore: Deleted session {session_id}")

    def get_all_sessions(self) -> List[str]:
        """返回所有 session_id 列表。"""
        return list(self._sessions.keys())

    def get_stats(self) -> Dict:
        """返回存储统计信息，供 /memory API 和调试使用。"""
        return {
            "total_sessions": len(self._sessions),
            "max_sessions": self._max_sessions,
            "max_history_per_session": self._max_history,
            "sessions": [
                {
                    "session_id": sid,
                    "message_count": len(mem.messages),
                    "created_at": mem.created_at,
                    "last_updated": mem.last_updated,
                }
                for sid, mem in self._sessions.items()
            ]
        }


# ── 进程级单例 ────────────────────────────────────────────────────────────────
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """获取全局 MemoryStore 单例，首次调用时创建。"""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


def reset_memory_store() -> None:
    """重置全局存储（主要用于单元测试）。"""
    global _memory_store
    _memory_store = None
