"""会话用例编排：历史加载、问答编排、消息持久化。"""
from __future__ import annotations

from typing import Callable, List, Optional

from langchain_core.messages import BaseMessage

from app.core.compression import dict_history_to_messages
from app.core.exceptions import NotFoundError
from app.gateway.request_context import new_request_id
from app.infrastructure.observability.metrics import inc
from app.infrastructure.persistence.conversations import get_conversation_store, messages_as_chat_history
from app.services.agent_service import ask, get_cached_ask

_ASSISTANT_META_KEYS = (
    "sources",
    "latency_ms",
    "grade",
    "request_id",
    "hitl_pending",
    "cached",
    "stream_id",
)


def ensure_conversation(user_sub: str, conversation_id: Optional[str]) -> str:
    store = get_conversation_store()
    if conversation_id:
        if not store.get_conversation(conversation_id, user_sub):
            raise NotFoundError("Conversation not found")
        return conversation_id
    conv = store.create_conversation(user_sub)
    return conv["conversation_id"]


def load_history_from_store(conversation_id: str) -> List[BaseMessage]:
    raw = get_conversation_store().list_messages(conversation_id)
    return dict_history_to_messages(messages_as_chat_history(raw))


def history_loader_for(conversation_id: str) -> Callable[[], List[BaseMessage]]:
    return lambda: load_history_from_store(conversation_id)


def persist_assistant_from_meta(
    conversation_id: str,
    meta: dict,
    *,
    full_answer: str,
    history_len: int,
    user_message: str,
) -> None:
    store = get_conversation_store()
    assistant_meta = {k: meta.get(k) for k in _ASSISTANT_META_KEYS if meta.get(k) is not None}
    final_answer = meta.get("answer") or full_answer
    store.append_message(conversation_id, "assistant", final_answer, metadata=assistant_meta)
    if meta.get("cached"):
        inc("cache_hits")
    if meta.get("hitl_pending"):
        inc("hitl_pending")
    if history_len == 0:
        title = user_message.strip().replace("\n", " ")[:80]
        store.touch_conversation(conversation_id, title=title or "New chat")


def run_chat(
    *,
    user_sub: str,
    user_role: str,
    conversation_id: str,
    message: str,
    hitl_approved: bool,
    use_cache: bool,
    agent_mode: str = "rag",
) -> dict:
    store = get_conversation_store()
    new_request_id()
    inc("requests_total")
    is_first_turn = len(store.list_messages(conversation_id)) == 0
    user_roles = [user_role, "public"]

    cached = get_cached_ask(
        message,
        user_roles=user_roles,
        conversation_id=conversation_id,
        use_cache=use_cache,
        agent_mode=agent_mode,
    )
    if cached is not None:
        store.append_message(conversation_id, "user", message)
        assistant_meta = {
            k: cached.get(k)
            for k in _ASSISTANT_META_KEYS
            if k in cached and cached.get(k) is not None
        }
        store.append_message(conversation_id, "assistant", cached.get("answer", ""), metadata=assistant_meta)
        if is_first_turn:
            title = message.strip().replace("\n", " ")[:80]
            store.touch_conversation(conversation_id, title=title or "New chat")
        if cached.get("cached"):
            inc("cache_hits")
        cached["role"] = user_role
        cached["conversation_id"] = conversation_id
        cached["thread_id"] = conversation_id
        return cached

    history = load_history_from_store(conversation_id)
    result = ask(
        message,
        history,
        user_roles=user_roles,
        thread_id=conversation_id,
        conversation_id=conversation_id,
        hitl_approved=hitl_approved,
        use_cache=use_cache,
        agent_mode=agent_mode,
    )

    store.append_message(conversation_id, "user", message)
    assistant_meta = {
        k: result.get(k)
        for k in _ASSISTANT_META_KEYS
        if k in result and result.get(k) is not None
    }
    store.append_message(conversation_id, "assistant", result.get("answer", ""), metadata=assistant_meta)

    if is_first_turn:
        title = message.strip().replace("\n", " ")[:80]
        store.touch_conversation(conversation_id, title=title or "New chat")

    if result.get("cached"):
        inc("cache_hits")
    if result.get("hitl_pending"):
        inc("hitl_pending")

    result["role"] = user_role
    result["conversation_id"] = conversation_id
    result["thread_id"] = conversation_id
    return result
