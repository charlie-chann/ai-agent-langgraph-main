"""HITL 相关 Schema。"""
from __future__ import annotations

from pydantic import BaseModel


class HITLResumeRequest(BaseModel):
    thread_id: str
    approved: bool = True
