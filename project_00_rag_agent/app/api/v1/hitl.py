"""HITL 人工审核路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import TokenPayload, get_conversation_store, require_permission
from app.schemas.hitl import HITLResumeRequest
from app.services.rag_service import resume_hitl

router = APIRouter(tags=["hitl"])


@router.post("/hitl/resume")
async def hitl_resume(
    req: HITLResumeRequest,
    user: TokenPayload = Depends(require_permission("hitl_approve")),
):
    result = resume_hitl(req.thread_id, approved=req.approved)
    if req.approved and result.get("answer"):
        store = get_conversation_store()
        conv = store.get_conversation(req.thread_id, user.sub)
        if conv:
            store.append_message(
                req.thread_id,
                "assistant",
                result["answer"],
                metadata={"hitl_resumed": True, "request_id": result.get("request_id")},
            )
    return result
