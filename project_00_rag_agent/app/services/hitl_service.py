"""HITL 人工审核用例编排。"""
from __future__ import annotations

from app.infrastructure.persistence.conversations import get_conversation_store
from app.services.agent_service import resume_hitl


def resume_hitl_conversation(thread_id: str, *, approved: bool, user_sub: str) -> dict:
    """恢复挂起的图执行，并在批准后将助手回复写入会话。"""
    result = resume_hitl(thread_id, approved=approved)
    if approved and result.get("answer"):
        store = get_conversation_store()
        conv = store.get_conversation(thread_id, user_sub)
        if conv:
            store.append_message(
                thread_id,
                "assistant",
                result["answer"],
                metadata={"hitl_resumed": True, "request_id": result.get("request_id")},
            )
    return result
