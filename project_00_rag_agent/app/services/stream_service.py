"""流式对话用例：SSE / WAL 生产与续推编排。"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.gateway.auth import TokenPayload
from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.stream_sse import consume_wal_sse, parse_last_event_id
from app.core.streaming import CancelToken
from app.gateway.request_context import new_request_id
from app.infrastructure.observability.metrics import inc
from app.infrastructure.persistence.conversations import get_conversation_store
from app.infrastructure.persistence.stream_wal import get_stream_status
from app.schemas.chat import ConversationChatRequest
from app.services.agent_service import ask_stream_async, get_stream_task, start_wal_stream_producer
from app.services.chat_service import ensure_conversation, history_loader_for, persist_assistant_from_meta


async def start_conversation_stream(
    *,
    conversation_id: str,
    req: ConversationChatRequest,
    request: Request,
    user: TokenPayload,
    last_event_id_header: Optional[str] = None,
) -> StreamingResponse:
    """启动或续推会话流式回答，返回 SSE StreamingResponse。"""
    ensure_conversation(user.sub, conversation_id)

    store = get_conversation_store()
    rid = new_request_id()
    inc("requests_total")

    after_offset = (
        req.last_event_id if req.last_event_id is not None else parse_last_event_id(last_event_id_header)
    )
    resume_stream_id = req.stream_id
    is_resume = bool(resume_stream_id and settings.stream_resume_enabled)
    is_first_turn = False

    if is_resume:
        meta = get_stream_status(resume_stream_id) or {}
        if meta.get("conversation_id") not in (None, conversation_id):
            raise ValidationError("stream_id does not belong to this conversation")
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
                history_loader=history_loader_for(conversation_id),
                user_roles=[user.role, "public"],
                hitl_approved=req.hitl_approved,
                use_cache=req.use_cache,
                agent_mode=req.agent_type,
            )

    cancel = CancelToken()
    use_wal = settings.stream_resume_enabled

    async def _gen() -> AsyncGenerator[str, None]:
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
                        persist_assistant_from_meta(
                            conversation_id,
                            meta,
                            full_answer=full_answer,
                            history_len=0 if is_first_turn and not is_resume else 1,
                            user_message=req.message,
                        )
                        persisted = True
                yield "id: 0\ndata: [DONE]\n\n"
                return

            offset = after_offset
            async for token in ask_stream_async(
                req.message,
                history_loader=history_loader_for(conversation_id),
                user_roles=[user.role, "public"],
                thread_id=conversation_id,
                conversation_id=conversation_id,
                hitl_approved=req.hitl_approved,
                use_cache=req.use_cache,
                cancel=cancel,
                agent_mode=req.agent_type,
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
            persist_assistant_from_meta(
                conversation_id,
                meta,
                full_answer=full_answer,
                history_len=0 if is_first_turn and not is_resume else 1,
                user_message=req.message,
            )
            offset += 1
            yield f"id: {offset}\ndata: [DONE]\n\n"
        finally:
            if cancel.is_cancelled and settings.stream_cancel_on_disconnect:
                task = get_stream_task(stream_id)
                if task and not task.done():
                    task.cancel()

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Stream-Id": stream_id,
            "X-Accel-Buffering": "no",
        },
    )


async def resume_stream(
    *,
    conversation_id: str,
    stream_id: str,
    request: Request,
    user: TokenPayload,
    last_event_id: Optional[str] = None,
    after: int = 0,
) -> StreamingResponse:
    """SSE 断线续推：从 WAL offset 精确续推。"""
    ensure_conversation(user.sub, conversation_id)

    meta = get_stream_status(stream_id)
    if not meta:
        raise NotFoundError("Stream not found or expired")
    if meta.get("conversation_id") != conversation_id:
        raise ValidationError("stream_id does not belong to this conversation")

    offset = after or parse_last_event_id(last_event_id)
    cancel = CancelToken()

    async def _gen() -> AsyncGenerator[str, None]:
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

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Stream-Id": stream_id},
    )
