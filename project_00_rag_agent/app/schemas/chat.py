"""对话与会话相关 Schema。"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

AgentType = Literal["rag", "react"]


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ChatRequest(BaseModel):
    """
    聊天请求。生产推荐 POST /conversations/{id}/chat，仅传 message。

    conversation_id 为空时自动创建新会话；chat_history 已废弃（由服务端从 DB 加载）。
    """

    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    chat_history: List[dict] = Field(default_factory=list, deprecated=True)
    thread_id: Optional[str] = None
    hitl_approved: bool = False
    use_cache: bool = True
    agent_type: AgentType = Field(default="rag", description="Agent 执行模式：rag | react")


class ConversationChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    hitl_approved: bool = False
    use_cache: bool = True
    agent_type: AgentType = Field(default="rag", description="Agent 执行模式：rag | react")
    stream_id: Optional[str] = Field(
        default=None,
        description="续推已有流；与 Last-Event-ID 配合使用",
    )
    last_event_id: Optional[int] = Field(
        default=None,
        description="WAL offset；也可通过 Last-Event-ID 请求头传入",
    )
