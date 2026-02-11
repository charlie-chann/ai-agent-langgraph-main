# memory.py — Conversation memory management
from typing import List, Dict, Optional
from datetime import datetime
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from dataclasses import dataclass, field
import json
import threading

from loguru import logger


@dataclass
class ConversationMemory:
    """In-memory conversation storage with persistence option."""
    
    session_id: str
    messages: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    
    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.messages.append({
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_updated = datetime.now().isoformat()
    
    def add_ai_message(self, content: str) -> None:
        """Add an AI message to history."""
        self.messages.append({
            "role": "ai",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.last_updated = datetime.now().isoformat()
    
    def add_tool_call(self, tool_name: str, input_data: str, output: str) -> None:
        """Add a tool call record."""
        self.messages.append({
            "role": "tool",
            "tool_name": tool_name,
            "input": input_data,
            "output": output,
            "timestamp": datetime.now().isoformat(),
        })
    
    def get_messages(self, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation history, optionally limited to last N messages."""
        if limit is None:
            return self.messages.copy()
        return self.messages[-limit:] if limit > 0 else self.messages.copy()
    
    def get_langchain_messages(self, limit: Optional[int] = None) -> List[BaseMessage]:
        """Convert to LangChain message format for agent."""
        history = self.get_messages(limit)
        result = []
        for msg in history:
            if msg["role"] == "user":
                result.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "ai":
                result.append(AIMessage(content=msg["content"]))
            # Skip tool messages in langchain format
        return result
    
    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
        self.last_updated = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "messages": self.messages,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationMemory":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            messages=data.get("messages", []),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_updated=data.get("last_updated", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class MemoryStore:
    """
    Global memory store for managing multiple conversation sessions.
    
    Usage:
        memory = MemoryStore()
        
        # Create a new session
        memory.create_session("user123")
        
        # Add messages
        memory.add_message("user123", "Hello", "user")
        memory.add_message("user123", "Hi there!", "ai")
        
        # Get history for agent
        history = memory.get_langchain_messages("user123")
        
        # Get history for display
        messages = memory.get_messages("user123")
    """
    
    def __init__(self, max_sessions: int = 1000, max_history_per_session: int = 100):
        """
        Initialize memory store.
        
        Args:
            max_sessions: Maximum number of concurrent sessions to store
            max_history_per_session: Maximum messages to keep per session
        """
        self._sessions: Dict[str, ConversationMemory] = {}
        self._lock = threading.RLock()
        self._max_sessions = max_sessions
        self._max_history = max_history_per_session
    
    def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> ConversationMemory:
        """Create a new conversation session."""
        with self._lock:
            if session_id in self._sessions:
                return self._sessions[session_id]
            
            # Cleanup old sessions if at capacity
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
        """Get an existing session."""
        return self._sessions.get(session_id)
    
    def get_or_create_session(self, session_id: str, metadata: Optional[Dict] = None) -> ConversationMemory:
        """Get existing session or create new one."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id, metadata)
        return session
    
    def add_message(self, session_id: str, content: str, role: str) -> None:
        """
        Add a message to session history.
        
        Args:
            session_id: Session identifier
            content: Message content
            role: "user", "ai", or "tool"
        """
        with self._lock:
            session = self.get_or_create_session(session_id)
            
            if role == "user":
                session.add_user_message(content)
            elif role == "ai":
                session.add_ai_message(content)
            elif role == "tool":
                # For tool calls, content is output, need tool_name and input
                pass  # Use add_tool_call instead
            
            # Trim if exceeds max history
            if len(session.messages) > self._max_history:
                session.messages = session.messages[-self._max_history:]
    
    def add_tool_call(self, session_id: str, tool_name: str, input_data: str, output: str) -> None:
        """Add a tool call record."""
        with self._lock:
            session = self.get_or_create_session(session_id)
            session.add_tool_call(tool_name, input_data, output)
    
    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get conversation messages."""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get_messages(limit)
    
    def get_langchain_messages(self, session_id: str, limit: Optional[int] = None) -> List[BaseMessage]:
        """Get messages in LangChain format for agent."""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.get_langchain_messages(limit)
    
    def clear_session(self, session_id: str) -> None:
        """Clear a session's history."""
        with self._lock:
            session = self.get_session(session_id)
            if session:
                session.clear()
                logger.info(f"MemoryStore: Cleared session {session_id}")
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session entirely."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"MemoryStore: Deleted session {session_id}")
    
    def get_all_sessions(self) -> List[str]:
        """Get list of all session IDs."""
        return list(self._sessions.keys())
    
    def get_stats(self) -> Dict:
        """Get memory store statistics."""
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


# ── Global singleton ─────────────────────────────────────────────────────────
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the global memory store singleton."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


def reset_memory_store() -> None:
    """Reset the global memory store."""
    global _memory_store
    _memory_store = None
