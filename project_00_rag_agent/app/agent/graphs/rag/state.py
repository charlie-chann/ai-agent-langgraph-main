"""
graphs/rag/state.py — RAG 流水线共享状态
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage


class RagState(TypedDict, total=False):
    """RAG 图各节点间传递的状态。"""

    question: str
    rewritten_question: str
    chat_history: List[BaseMessage]
    context_docs: List[Document]
    kg_context: str
    sources: List[str]
    conflicts: str
    answer: str
    grade: str
    grade_reason: str
    iterations: int
    latency_ms: float
    disclaimer: str
    error: Optional[str]
    user_roles: List[str]
    request_id: str
    hitl_required: bool
    hitl_approved: bool
