"""
agent.py — project_00_rag_agent 对外公共 API

【职责】
封装 LangGraph RAG 工作流的同步/流式问答入口，以及 HITL 恢复、启动预热、
运行态统计等运维接口；供 api.py、测试脚本、外部服务调用。

【设计原因】
1. 与 graph/ 分层：图构建与节点逻辑在 graph/ 包，本模块只做「组装 + 缓存 + 返回格式」
2. ask() 走完整图（含 guard、grade 重试、HITL 中断），ask_stream() 为 UI 体验做流式取舍
3. Redis 缓存键按 question + roles 去重，HITL 中断或出错时不写缓存，避免脏数据

【与 project_01 差异】
- project_01 的 agent.py 内联了 LangGraph 节点与 build_rag_graph；本模块仅调用 graph.builder
- 新增：RBAC user_roles、HITL resume_hitl、Redis 缓存、request_id 追踪、
  对话历史压缩、KG/冲突/disclaimer 等扩展字段
- ask_stream 显式调用 node_guard / node_rewrite / node_retrieve，并注入 kg_context、conflicts
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Generator, List, Optional

from langchain_core.messages import BaseMessage
from loguru import logger

from config import settings
from core.compression import compress_chat_history, dict_history_to_messages
from graph.builder import get_graph, reset_graph
from graph.state import RAGState
from middleware.cache import cache_get, cache_key, cache_set
from middleware.request_context import get_request_id, new_request_id
from providers.factory import get_chat_model
from prompts.rag_prompts import rag_prompt
from tools.retriever import rebuild_bm25_from_chroma, retrieve_with_kg


def _base_state(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    hitl_approved: bool = False,
) -> RAGState:
    """
    构造 LangGraph 初始状态字典。

    统一填充 question、rewritten_question、chat_history、iterations 等必填字段，
    并从请求上下文注入 request_id；默认角色为 viewer（最低权限）。
    """
    return {
        "question": question,
        "rewritten_question": question,
        "chat_history": chat_history or [],
        "iterations": 0,
        "user_roles": user_roles or ["viewer"],
        "request_id": get_request_id() or new_request_id(),
        "hitl_approved": hitl_approved,
        "hitl_required": False,
    }


def _cache_key_for_ask(
    question: str,
    user_roles: Optional[List[str]],
    chat_history: List[BaseMessage],
    conversation_id: Optional[str],
) -> str:
    """多轮会话下缓存键需含会话或历史摘要，避免不同上下文误命中。"""
    payload: dict = {"q": question, "roles": user_roles}
    if conversation_id:
        payload["conv"] = conversation_id
    elif chat_history:
        sig = "|".join(f"{type(m).__name__}:{getattr(m, 'content', '')}" for m in chat_history[-6:])
        payload["hist"] = hashlib.sha256(sig.encode()).hexdigest()[:16]
    return cache_key("ask", payload)


def ask(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    hitl_approved: bool = False,
    use_cache: bool = True,
    return_state: bool = False,
) -> dict:
    """
    同步问答：跑完整个 LangGraph（含 guard、可能的重试循环与 HITL），返回结构化结果。

    流程：压缩历史 → 查 Redis 缓存 → invoke 图 → 组装 answer/sources 等字段；
    HITL 待审批或出错时不写入缓存。
    """
    history = compress_chat_history(chat_history or [])
    ck = _cache_key_for_ask(question, user_roles, history, conversation_id)
    if use_cache and settings.cache_enabled:
        cached = cache_get(ck)
        if cached:
            cached["cached"] = True
            return cached

    # conversation_id 与 thread_id 对齐，便于 HITL 与聊天记录关联
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    state = get_graph().invoke(
        _base_state(question, history, user_roles, thread_id, hitl_approved),
        config=config,
    )

    # 检测 HITL 中断：需要人工审批且尚未 approved
    interrupted = state.get("hitl_required") and not state.get("hitl_approved")

    result = {
        "answer": state.get("answer", ""),
        "sources": state.get("sources", []),
        "latency_ms": state.get("latency_ms", 0),
        "iterations": state.get("iterations", 1),
        "grade": state.get("grade", "unknown"),
        "error": state.get("error"),
        "disclaimer": state.get("disclaimer", ""),
        "conflicts": state.get("conflicts", ""),
        "request_id": state.get("request_id"),
        "hitl_pending": interrupted,
        "thread_id": effective_thread,
        "conversation_id": conversation_id,
        "cached": False,
    }
    # 仅成功完成且无 HITL 挂起时写缓存
    if use_cache and not interrupted and not state.get("error"):
        cache_set(ck, result)
    if return_state:
        result["state"] = state
    return result


def resume_hitl(thread_id: str, approved: bool = True) -> dict:
    """
    HITL 恢复：人工审批后继续或拒绝挂起的图执行。

    approved=False 时直接写入拒绝文案并结束；True 时更新 hitl_approved 再 invoke(None) 从断点继续。
    """
    config = {"configurable": {"thread_id": thread_id}}
    graph = get_graph()
    snapshot = graph.get_state(config)
    if not snapshot or not snapshot.values:
        return {"error": "No pending thread", "thread_id": thread_id}

    if not approved:
        graph.update_state(config, {"hitl_approved": False, "answer": "Request rejected by reviewer."})
        return {"answer": "Request rejected by reviewer.", "hitl_pending": False, "thread_id": thread_id}

    graph.update_state(config, {"hitl_approved": True})
    # invoke(None) 表示从 Checkpointer 快照继续，不传入新初始 state
    state = graph.invoke(None, config=config)
    return {
        "answer": state.get("answer", ""),
        "sources": state.get("sources", []),
        "hitl_pending": False,
        "thread_id": thread_id,
        "request_id": state.get("request_id"),
    }


def ask_stream(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    user_roles: Optional[List[str]] = None,
    conversation_id: Optional[str] = None,
) -> Generator[str, None, None]:
    """
    流式问答：guard → rewrite → retrieve 后逐 token 输出，末尾附带 __META__ JSON。

    【设计取舍】
    与 project_01 相同：流式路径不跑完整 grade 重试循环，避免用户等多轮检索才看到首字。
    流式结束后仍调用 node_generate / node_grade 仅用于生成 __META__ 中的 sources、grade 等。
    """
    from graph.nodes import node_generate, node_grade, node_guard, node_rewrite, node_retrieve

    history = compress_chat_history(chat_history or [])
    temp: RAGState = _base_state(question, history, user_roles)
    if conversation_id:
        temp["request_id"] = temp.get("request_id") or conversation_id
    temp = node_guard(temp)
    if temp.get("error") == "blocked":
        yield temp.get("answer", "Blocked")
        return

    temp = node_rewrite(temp)
    temp = node_retrieve(temp)

    chunks = [d.page_content for d in temp.get("context_docs", [])]
    from core.compression import trim_context_chunks
    # 按 token 预算截断上下文，高排名 chunk 应排在前面
    context = trim_context_chunks(chunks)

    chain = rag_prompt | get_chat_model(streaming=True)
    t0 = time.perf_counter()
    for chunk in chain.stream({
        "context": context or "(no context)",
        "kg_context": temp.get("kg_context") or "(none)",
        "conflicts": temp.get("conflicts") or "",
        "question": question,
        "chat_history": history,
    }):
        yield chunk.content

    # 流式正文已输出；以下节点主要用于统计与 meta，不再次 yield 正文
    temp = node_generate(temp)
    temp = node_grade(temp)
    meta = json.dumps({
        "sources": temp.get("sources", []),
        "latency_ms": round((time.perf_counter() - t0) * 1000),
        "grade": temp.get("grade"),
        "request_id": temp.get("request_id"),
        "__meta__": True,
    })
    yield f"\n\n__META__{meta}"


def startup():
    """
    应用启动时调用：从 Chroma 重建 BM25 稀疏索引（若 pickle 缺失或需同步）。

    保证 hybrid/sparse 检索模式在 API 启动后立即可用。
    """
    n = rebuild_bm25_from_chroma()
    logger.info(f"Startup: rebuilt BM25 with {n} chunks")


def get_stats() -> dict:
    """
    返回当前检索层与熔断器运行态，便于 /health 或监控面板展示。
    """
    from tools.knowledge_graph import get_kg
    from tools.retriever import _chunks, get_vectorstore
    from core.circuit_breaker import llm_breaker, embed_breaker

    try:
        count = get_vectorstore()._collection.count()
    except Exception:
        count = 0
    return {
        "documents_indexed": count,
        "bm25_chunks": len(_chunks),
        "kg_triples": len(get_kg().triples),
        "retrieval_mode": settings.retrieval_mode,
        "llm_provider": settings.llm_provider,
        "circuit_breakers": [llm_breaker.status(), embed_breaker.status()],
    }
