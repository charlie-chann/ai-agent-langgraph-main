"""RAG LangGraph 工作流构建。"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.agent.checkpointer import get_checkpointer
from app.agent.graphs.rag.edges import route_after_guard, should_retry
from app.agent.graphs.rag.nodes import (
    node_generate,
    node_grade,
    node_guard,
    node_hitl_gate,
    node_retrieve,
    node_rewrite,
)
from app.agent.graphs.rag.state import RagState


def build_graph(*, with_checkpointer: bool = True):
    """构建并编译 RAG LangGraph。"""
    g = StateGraph(RagState)

    g.add_node("guard", node_guard)
    g.add_node("hitl_gate", node_hitl_gate)
    g.add_node("rewrite", node_rewrite)
    g.add_node("retrieve", node_retrieve)
    g.add_node("generate", node_generate)
    g.add_node("grade", node_grade)

    g.set_entry_point("guard")
    g.add_conditional_edges("guard", route_after_guard, {
        END: END,
        "hitl_gate": "hitl_gate",
        "rewrite": "rewrite",
    })
    g.add_edge("hitl_gate", "rewrite")
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "grade")
    g.add_conditional_edges("grade", should_retry, {"rewrite": "rewrite", END: END})

    interrupt_before = ["hitl_gate"] if settings.hitl_enabled else []
    if with_checkpointer:
        return g.compile(checkpointer=get_checkpointer(), interrupt_before=interrupt_before)
    return g.compile(interrupt_before=interrupt_before)
