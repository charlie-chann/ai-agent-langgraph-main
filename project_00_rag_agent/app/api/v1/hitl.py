"""HITL 人工审核路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import TokenPayload, require_permission
from app.schemas.hitl import HITLResumeRequest
from app.services.hitl_service import resume_hitl_conversation

router = APIRouter(tags=["hitl"])


@router.post("/hitl/resume")
async def hitl_resume(
    req: HITLResumeRequest,
    user: TokenPayload = Depends(require_permission("hitl_approve")),
):
    """管理员审批后恢复被 HITL 挂起的线程。"""
    return resume_hitl_conversation(req.thread_id, approved=req.approved, user_sub=user.sub)
