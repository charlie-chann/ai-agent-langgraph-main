"""
graph/state.py — LangGraph 全局状态定义

【职责】
定义 RAG 工作流在各节点间传递的共享状态结构 RAGState。

【设计原因】
1. 使用 TypedDict：LangGraph 要求状态为 dict-like 结构，TypedDict 提供字段类型提示而不引入运行时开销
2. total=False：所有字段可选，节点按需读写，避免 invoke 时必须传入完整初始状态
3. 状态与节点解耦：字段集中在此文件，nodes/edges/builder 只依赖类型契约，便于扩展新节点
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage


class RAGState(TypedDict, total=False):
    """
    LangGraph 全局状态 — 每个节点读取并更新其中的字段。

    典型流转：guard → rewrite → retrieve → generate → grade →（可能回到 rewrite）
    """

    # ── 用户输入 ─────────────────────────────────────────────────────────────
    question: str                      # 用户原始问题
    rewritten_question: str            # 改写后用于检索的问题（首次等于原问题）
    chat_history: List[BaseMessage]    # 多轮对话历史，注入 rag_prompt

    # ── 检索结果 ─────────────────────────────────────────────────────────────
    context_docs: List[Document]       # 向量检索 + 精排后的文档片段
    kg_context: str                    # 知识图谱补充上下文（实体/关系证据）
    sources: List[str]                 # 去重后的来源文件名，供 UI/API 展示引用
    conflicts: str                     # 多文档冲突摘要（格式化后的文本）

    # ── 生成与评分 ───────────────────────────────────────────────────────────
    answer: str                        # LLM 生成的最终回答
    grade: str                         # 评分结果："yes" | "no"
    grade_reason: str                  # 评分理由（调试与审计用）
    iterations: int                    # 已完成的评分轮数（控制重试上限）
    latency_ms: float                  # generate 节点耗时（毫秒）
    disclaimer: str                    # 降级/未 grounded 时的免责声明

    # ── 错误与拦截 ───────────────────────────────────────────────────────────
    error: Optional[str]               # 各环节错误码或消息（如 "blocked"）

    # ── 权限与可观测性 ───────────────────────────────────────────────────────
    user_roles: List[str]              # RBAC 角色列表，检索时过滤可见文档
    request_id: str                    # 请求追踪 ID，贯穿日志与 metrics

    # ── HITL（Human-in-the-Loop）──────────────────────────────────────────────
    hitl_required: bool                # 是否命中高风险关键词，需人工审批
    hitl_approved: bool                # 人工是否已批准继续（checkpointer 恢复后设为 True）
