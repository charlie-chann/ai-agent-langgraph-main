"""对话 / 会话路由。"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.deps import TokenPayload, get_conversation_store, require_permission
from app.core.compression import dict_history_to_messages
from app.core.stream_sse import consume_wal_sse, parse_last_event_id
from app.core.streaming import CancelToken
from app.gateway.request_context import new_request_id
from app.infrastructure.observability.metrics import inc
from app.infrastructure.persistence.conversations import messages_as_chat_history
from app.infrastructure.persistence.stream_wal import get_stream_status
from app.schemas.chat import ChatRequest, ConversationChatRequest, CreateConversationRequest
from app.services.rag_service import (
    ask,
    ask_stream_async,
    get_cached_ask,
    get_stream_task,
    start_wal_stream_producer,
)
from config import settings

router = APIRouter(tags=["chat"])


def _persist_assistant_from_meta(
    store,
    conversation_id: str,
    meta: dict,
    *,
    full_answer: str,
    history_len: int,
    user_message: str,
) -> None:
    assistant_meta = {
        k: meta.get(k)
        for k in ("sources", "latency_ms", "grade", "request_id", "hitl_pending", "cached", "stream_id")
        if meta.get(k) is not None
    }
    final_answer = meta.get("answer") or full_answer
    store.append_message(conversation_id, "assistant", final_answer, metadata=assistant_meta)
    if meta.get("cached"):
        inc("cache_hits")
    if meta.get("hitl_pending"):
        inc("hitl_pending")
    if history_len == 0:
        title = user_message.strip().replace("\n", " ")[:80]
        store.touch_conversation(conversation_id, title=title or "New chat")


def _ensure_conversation(user: TokenPayload, conversation_id: Optional[str]) -> str:
    store = get_conversation_store()
    if conversation_id:
        conv = store.get_conversation(conversation_id, user.sub)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation_id
    conv = store.create_conversation(user.sub)
    return conv["conversation_id"]


def _load_history_from_store(conversation_id: str) -> list:
    raw = get_conversation_store().list_messages(conversation_id)
    return dict_history_to_messages(messages_as_chat_history(raw))


def _run_chat(
    *,
    user: TokenPayload,
    conversation_id: str,
    message: str,
    hitl_approved: bool,
    use_cache: bool,
) -> dict:
    store = get_conversation_store()
    new_request_id()
    inc("requests_total")
    is_first_turn = len(store.list_messages(conversation_id)) == 0

    cached = get_cached_ask(
        message,
        user_roles=[user.role, "public"],
        conversation_id=conversation_id,
        use_cache=use_cache,
    )
    if cached is not None:
        store.append_message(conversation_id, "user", message)
        assistant_meta = {
            k: cached.get(k)
            for k in ("sources", "latency_ms", "grade", "request_id", "hitl_pending", "cached")
            if cached.get(k) is not None
        }
        store.append_message(conversation_id, "assistant", cached.get("answer", ""), metadata=assistant_meta)
        if is_first_turn:
            title = message.strip().replace("\n", " ")[:80]
            store.touch_conversation(conversation_id, title=title or "New chat")
        if cached.get("cached"):
            inc("cache_hits")
        cached["role"] = user.role
        cached["conversation_id"] = conversation_id
        cached["thread_id"] = conversation_id
        return cached

    history = _load_history_from_store(conversation_id)
    result = ask(
        message,
        history,
        user_roles=[user.role, "public"],
        thread_id=conversation_id,
        conversation_id=conversation_id,
        hitl_approved=hitl_approved,
        use_cache=use_cache,
    )

    store.append_message(conversation_id, "user", message)
    assistant_meta = {
        k: result.get(k)
        for k in ("sources", "latency_ms", "grade", "request_id", "hitl_pending", "cached")
        if result.get(k) is not None
    }
    store.append_message(conversation_id, "assistant", result.get("answer", ""), metadata=assistant_meta)

    if is_first_turn:
        title = message.strip().replace("\n", " ")[:80]
        store.touch_conversation(conversation_id, title=title or "New chat")

    if result.get("cached"):
        inc("cache_hits")
    if result.get("hitl_pending"):
        inc("hitl_pending")

    result["role"] = user.role
    result["conversation_id"] = conversation_id
    result["thread_id"] = conversation_id
    return result


@router.post("/conversations")
async def create_conversation(
    req: CreateConversationRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """创建新会话，返回 conversation_id（后续 chat 只需传此 ID + message）。"""
    conv = get_conversation_store().create_conversation(user.sub, title=req.title)
    return conv


@router.get("/conversations")
async def list_conversations(
    user: TokenPayload = Depends(require_permission("chat")),
    limit: int = 50,
):
    return {"conversations": get_conversation_store().list_conversations(user.sub, limit=limit)}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: TokenPayload = Depends(require_permission("chat")),
):
    store = get_conversation_store()
    if not store.get_conversation(conversation_id, user.sub):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": store.list_messages(conversation_id),
    }


@router.post("/conversations/{conversation_id}/chat")
async def conversation_chat(
    conversation_id: str,
    req: ConversationChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """生产推荐：服务端从 DB 加载 chat_history，客户端只发 message。"""
    _ensure_conversation(user, conversation_id)
    return _run_chat(
        user=user,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )


@router.post("/conversations/{conversation_id}/chat/stream")
async def conversation_chat_stream(
    conversation_id: str,
    req: ConversationChatRequest,
    request: Request,
    user: TokenPayload = Depends(require_permission("chat")),
    last_event_id_header: Optional[str] = Header(default=None, alias="Last-Event-ID"),
):
    _ensure_conversation(user, conversation_id)
    store = get_conversation_store()
    rid = new_request_id()
    inc("requests_total")

    after_offset = req.last_event_id if req.last_event_id is not None else parse_last_event_id(last_event_id_header)
    resume_stream_id = req.stream_id
    is_resume = bool(resume_stream_id and settings.stream_resume_enabled)
    is_first_turn = False

    if is_resume:
        meta = get_stream_status(resume_stream_id) or {}
        if meta.get("conversation_id") not in (None, conversation_id):
            raise HTTPException(status_code=400, detail="stream_id does not belong to this conversation")
        stream_id = resume_stream_id
    else:
        is_first_turn = len(store.list_messages(conversation_id)) == 0
        store.append_message(conversation_id, "user", req.message)
        stream_id = rid
        if settings.stream_resume_enabled:
            await start_wal_stream_producer(
                stream_id=stream_id,
                conversation_id=conversation_id,
                question=req.message,
                history_loader=lambda: _load_history_from_store(conversation_id),
                user_roles=[user.role, "public"],
                hitl_approved=req.hitl_approved,
                use_cache=req.use_cache,
            )

    cancel = CancelToken()
    use_wal = settings.stream_resume_enabled

    async def _gen():
        full_answer = ""
        meta: dict = {"stream_id": stream_id, "conversation_id": conversation_id}
        persisted = False
        try:
            if use_wal:
                async for chunk in consume_wal_sse(
                    stream_id,
                    after_offset=after_offset,
                    extra_meta={"conversation_id": conversation_id, "stream_id": stream_id},
                    cancel=cancel,
                ):
                    if await request.is_disconnected():
                        if settings.stream_cancel_on_disconnect:
                            cancel.cancel()
                        break
                    yield chunk
                    if chunk.startswith("id:"):
                        lines = chunk.strip().split("\n")
                        data_line = next((ln for ln in lines if ln.startswith("data:")), "")
                        payload_raw = data_line[5:].strip()
                        if payload_raw == "[DONE]":
                            continue
                        try:
                            payload = json.loads(payload_raw)
                        except json.JSONDecodeError:
                            continue
                        if "token" in payload:
                            full_answer += payload["token"]
                        elif payload.get("__meta__") or "answer" in payload:
                            meta.update(payload)
                status = get_stream_status(stream_id) or {}
                if status.get("status") == "complete" and not persisted:
                    if meta.get("answer") or full_answer:
                        _persist_assistant_from_meta(
                            store,
                            conversation_id,
                            meta,
                            full_answer=full_answer,
                            history_len=is_first_turn if not is_resume else 1,
                            user_message=req.message,
                        )
                        persisted = True
                yield "id: 0\ndata: [DONE]\n\n"
                return

            offset = after_offset
            async for token in ask_stream_async(
                req.message,
                history_loader=lambda: _load_history_from_store(conversation_id),
                user_roles=[user.role, "public"],
                thread_id=conversation_id,
                conversation_id=conversation_id,
                hitl_approved=req.hitl_approved,
                use_cache=req.use_cache,
                cancel=cancel,
            ):
                if await request.is_disconnected():
                    if settings.stream_cancel_on_disconnect:
                        cancel.cancel()
                    break
                if token.startswith("\n\n__META__"):
                    meta = json.loads(token.replace("\n\n__META__", ""))
                    offset += 1
                    payload = {**meta, "conversation_id": conversation_id, "stream_id": stream_id}
                    yield f"id: {offset}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                else:
                    full_answer += token
                    offset += 1
                    yield f"id: {offset}\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
            _persist_assistant_from_meta(
                store,
                conversation_id,
                meta,
                full_answer=full_answer,
                history_len=is_first_turn if not is_resume else 1,
                user_message=req.message,
            )
            offset += 1
            yield f"id: {offset}\ndata: [DONE]\n\n"
        finally:
            if cancel.is_cancelled and settings.stream_cancel_on_disconnect:
                task = get_stream_task(stream_id)
                if task and not task.done():
                    task.cancel()

    headers = {
        "Cache-Control": "no-cache",
        "X-Stream-Id": stream_id,
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)


@router.get("/conversations/{conversation_id}/stream/{stream_id}")
async def resume_conversation_stream(
    conversation_id: str,
    stream_id: str,
    request: Request,
    user: TokenPayload = Depends(require_permission("chat")),
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    after: int = 0,
):
    """SSE 断线续推：带 Last-Event-ID 或 ?after=N 从 WAL offset 精确续推。"""
    _ensure_conversation(user, conversation_id)
    meta = get_stream_status(stream_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Stream not found or expired")
    if meta.get("conversation_id") != conversation_id:
        raise HTTPException(status_code=400, detail="stream_id does not belong to this conversation")

    offset = after or parse_last_event_id(last_event_id)
    cancel = CancelToken()

    async def _gen():
        try:
            async for chunk in consume_wal_sse(
                stream_id,
                after_offset=offset,
                extra_meta={"conversation_id": conversation_id, "stream_id": stream_id},
                cancel=cancel,
            ):
                if await request.is_disconnected():
                    if settings.stream_cancel_on_disconnect:
                        cancel.cancel()
                    break
                yield chunk
            yield "id: 0\ndata: [DONE]\n\n"
        finally:
            if cancel.is_cancelled:
                pass

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Stream-Id": stream_id},
    )


@router.post("/chat")
async def chat(
    req: ChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """
    兼容入口：未传 conversation_id 时自动创建会话。
    chat_history 字段已废弃，历史一律从服务端 DB 读取。
    """
    if req.chat_history:
        logger.warning("chat_history in request body is deprecated; using server-side conversation store")
    conversation_id = _ensure_conversation(user, req.conversation_id)
    return _run_chat(
        user=user,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    user: TokenPayload = Depends(require_permission("chat")),
):
    conversation_id = _ensure_conversation(user, req.conversation_id)
    fake = ConversationChatRequest(
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )
    return await conversation_chat_stream(conversation_id, fake, request, user)
