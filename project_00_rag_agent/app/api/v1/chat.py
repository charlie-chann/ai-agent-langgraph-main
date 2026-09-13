"""对话 / 会话路由。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from loguru import logger

from app.api.deps import TokenPayload, get_conversation_store, require_permission
from app.core.exceptions import NotFoundError, ValidationError
from app.schemas.chat import ChatRequest, ConversationChatRequest, CreateConversationRequest
from app.services.chat_service import ensure_conversation, run_chat
from app.services.stream_service import resume_stream, start_conversation_stream

router = APIRouter(tags=["chat"])


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
    """列出当前用户的会话列表。"""
    return {"conversations": get_conversation_store().list_conversations(user.sub, limit=limit)}


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """获取指定会话的历史消息。"""
    try:
        ensure_conversation(user.sub, conversation_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return {
        "conversation_id": conversation_id,
        "messages": get_conversation_store().list_messages(conversation_id),
    }


@router.post("/conversations/{conversation_id}/chat")
async def conversation_chat(
    conversation_id: str,
    req: ConversationChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """生产推荐：服务端从 DB 加载 chat_history，客户端只发 message。"""
    try:
        ensure_conversation(user.sub, conversation_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return run_chat(
        user_sub=user.sub,
        user_role=user.role,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
        agent_mode=req.agent_type,
    )


@router.post("/conversations/{conversation_id}/chat/stream")
async def conversation_chat_stream(
    conversation_id: str,
    req: ConversationChatRequest,
    request: Request,
    user: TokenPayload = Depends(require_permission("chat")),
    last_event_id_header: Optional[str] = Header(default=None, alias="Last-Event-ID"),
):
    """按 conversation_id 发起 SSE 流式对话。"""
    try:
        return await start_conversation_stream(
            conversation_id=conversation_id,
            req=req,
            request=request,
            user=user,
            last_event_id_header=last_event_id_header,
        )
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
    try:
        return await resume_stream(
            conversation_id=conversation_id,
            stream_id=stream_id,
            request=request,
            user=user,
            last_event_id=last_event_id,
            after=after,
        )
    except (NotFoundError, ValidationError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


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
    conversation_id = ensure_conversation(user.sub, req.conversation_id)
    return run_chat(
        user_sub=user.sub,
        user_role=user.role,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
        agent_mode=req.agent_type,
    )


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    request: Request,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """兼容入口：自动确保会话后转发到流式对话。"""
    conversation_id = ensure_conversation(user.sub, req.conversation_id)
    fake = ConversationChatRequest(
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
        agent_type=req.agent_type,
    )
    return await conversation_chat_stream(conversation_id, fake, request, user)
