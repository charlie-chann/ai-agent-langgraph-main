"""
graph/builder.py — LangGraph 工作流构建与编译

【职责】
注册节点与边、配置 HITL 中断点与 checkpointer，提供全局图单例 get_graph()。

【设计原因】
1. builder 与 nodes/edges 分离：改拓扑只动本文件，节点实现可独立演进
2. interrupt_before + checkpointer：HITL 需在 hitl_gate 前持久化状态，人工批准后用同一 thread_id 恢复
3. 懒加载单例 _graph：避免 import 时即编译图（依赖 settings、checkpointer 可能尚未就绪）
4. reset_graph：测试或配置热更新时清空单例与 checkpointer，强制下次 rebuild
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from config import settings
from app.agent.graph.checkpointer import get_checkpointer
from app.agent.graph.edges import route_after_guard, should_retry
from app.agent.graph.nodes import (
    node_generate,
    node_grade,
    node_guard,
    node_hitl_gate,
    node_retrieve,
    node_rewrite,
)
from app.agent.graph.state import RAGState

_graph = None  # 编译后的图单例，避免重复 build


def build_rag_graph(*, with_checkpointer: bool = True):
    """
    构建并编译 RAG LangGraph。

    图结构（主路径）：
      guard → rewrite → retrieve → generate → grade
                    ↑__________________________|  (grade=no 且未超限)

    HITL 分支：
      guard → hitl_gate → rewrite → ...（interrupt_before 在 hitl_gate 前暂停）

    Args:
        with_checkpointer: True 时挂载 Postgres/Memory checkpointer，支持 HITL 断点续跑
    """
    g = StateGraph(RAGState)

    # ── 注册节点 ─────────────────────────────────────────────────────────────
    g.add_node("guard", node_guard)
    g.add_node("hitl_gate", node_hitl_gate)
    g.add_node("rewrite", node_rewrite)
    g.add_node("retrieve", node_retrieve)
    g.add_node("generate", node_generate)
    g.add_node("grade", node_grade)

    # ── 入口与边 ─────────────────────────────────────────────────────────────
    g.set_entry_point("guard")
    g.add_conditional_edges("guard", route_after_guard, {
        END: END,
        "hitl_gate": "hitl_gate",
        "rewrite": "rewrite",
    })
    g.add_edge("hitl_gate", "rewrite")       # 人审通过后继续标准 RAG 链路
    g.add_edge("rewrite", "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", "grade")
    g.add_conditional_edges("grade", should_retry, {"rewrite": "rewrite", END: END})

    # HITL 开启时在 hitl_gate 前中断；关闭时不中断，risk 词仅标记不暂停
    interrupt_before = ["hitl_gate"] if settings.hitl_enabled else []
    if with_checkpointer:
        return g.compile(checkpointer=get_checkpointer(), interrupt_before=interrupt_before)
    return g.compile(interrupt_before=interrupt_before)


def get_graph():
    """懒加载获取已编译的 RAG 图（进程内单例）。"""
    global _graph
    if _graph is None:
        _graph = build_rag_graph()
    return _graph


def reset_graph():
    """测试/配置变更用：重置图单例并清空 checkpointer 缓存。"""
    global _graph
    _graph = None
    from app.agent.graph.checkpointer import reset_checkpointer
    reset_checkpointer()
