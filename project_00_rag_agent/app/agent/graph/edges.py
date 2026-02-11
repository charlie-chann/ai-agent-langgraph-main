"""
graph/edges.py — LangGraph 条件路由（conditional edges）

【职责】
定义 grade / guard 之后的分支逻辑：何时 END、何时回到 rewrite、何时进入 HITL 门控。

【设计原因】
1. 路由与节点分离：edges 只做「读 state → 返回下一节点名」，不含 LLM/检索等业务逻辑
2. 纯函数：便于单测（构造 mock state 断言返回值）且与 builder 中 add_conditional_edges 映射表对应
3. 集中引用 settings.max_iterations：重试上限与 config 一致，避免 magic number 散落
"""
from __future__ import annotations

from langgraph.graph import END

from config import settings
from app.agent.graph.state import RAGState


def route_after_guard(state: RAGState) -> str:
    """
    guard 节点之后的条件路由。

    优先级：
    1. error==blocked → END（安全拦截，不再检索/生成）
    2. hitl_required 且未批准 → hitl_gate（图在 interrupt_before 处暂停等人审）
    3. 否则 → rewrite（正常 RAG 主路径）
    """
    if state.get("error") == "blocked":
        return END
    if state.get("hitl_required") and not state.get("hitl_approved"):
        return "hitl_gate"
    return "rewrite"


def should_retry(state: RAGState) -> str:
    """
    grade 节点之后的条件路由：决定是否进入 Agentic 重试循环。

    grade=no 且 iterations < max_iterations → rewrite（改写问题重新检索）
    否则 → END（含：评分通过、或已达重试上限）
    """
    if state.get("grade") == "no" and state.get("iterations", 0) < settings.max_iterations:
        return "rewrite"
    return END
