"""
agent.py — project_00_rag_agent 对外公共 API

【职责】
封装 LangGraph RAG 工作流的同步/流式问答入口，以及 HITL 恢复、启动预热、
运行态统计等运维接口；供 api.py、测试脚本、外部服务调用。

【设计原因】
1. 与 graph/ 分层：图构建与节点逻辑在 graph/ 包，本模块只做「组装 + 缓存 + 返回格式」
2. ask() 使用 LangGraph invoke；ask_stream() 使用 astream（updates + custom token）
3. ask_stream() 与 ask() 共用压缩、缓存与全图能力（含 grade 重试、HITL）
4. Redis 缓存键按 question + roles 去重，HITL 中断或出错时不写缓存，避免脏数据

【与 project_01 差异】
- project_01 的 agent.py 内联了 LangGraph 节点与 build_rag_graph；本模块仅调用 graph.builder
- 新增：RBAC user_roles、HITL resume_hitl、Redis 缓存、request_id 追踪、
  对话历史压缩、KG/冲突/disclaimer 等扩展字段
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import AsyncGenerator, Generator, List, Optional

from langchain_core.messages import BaseMessage
from loguru import logger

from config import settings
from core.compression import compress_chat_history, dict_history_to_messages
from graph.builder import get_graph, reset_graph
from graph.state import RAGState
from middleware.cache import cache_get, cache_key, cache_set
from middleware.request_context import get_request_id, new_request_id
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


def _result_from_state(
    state: RAGState,
    *,
    conversation_id: Optional[str],
    effective_thread: str,
    cached: bool = False,
) -> dict:
    interrupted = state.get("hitl_required") and not state.get("hitl_approved")
    return {
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
        "cached": cached,
    }


def _invoke_rag_graph(
    question: str,
    history: List[BaseMessage],
    *,
    user_roles: Optional[List[str]],
    thread_id: Optional[str],
    conversation_id: Optional[str],
    hitl_approved: bool,
) -> tuple[RAGState, str]:
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    state = get_graph().invoke(
        _base_state(question, history, user_roles, thread_id, hitl_approved),
        config=config,
    )
    return state, effective_thread


def _maybe_cache_result(ck: str, result: dict, state: RAGState, *, use_cache: bool) -> None:
    if use_cache and not result.get("hitl_pending") and not state.get("error"):
        cache_set(ck, result)


def _meta_payload(result: dict) -> dict:
    keys = (
        "answer",
        "sources",
        "latency_ms",
        "grade",
        "request_id",
        "hitl_pending",
        "cached",
        "error",
        "disclaimer",
        "conflicts",
        "iterations",
        "thread_id",
        "conversation_id",
    )
    bool_keys = {"cached", "hitl_pending"}
    meta = {}
    for k in keys:
        if k not in result:
            continue
        if result[k] is not None or k in bool_keys:
            meta[k] = result[k]
    meta["__meta__"] = True
    return meta


def _iter_answer_chunks(text: str, chunk_size: int) -> Generator[str, None, None]:
    if not text:
        return
    if chunk_size <= 0:
        yield text
        return
    for i in range(0, len(text), chunk_size):
        yield text[i : i + chunk_size]


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

    state, effective_thread = _invoke_rag_graph(
        question,
        history,
        user_roles=user_roles,
        thread_id=thread_id,
        conversation_id=conversation_id,
        hitl_approved=hitl_approved,
    )
    result = _result_from_state(
        state,
        conversation_id=conversation_id,
        effective_thread=effective_thread,
    )
    _maybe_cache_result(ck, result, state, use_cache=use_cache)
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


def _merge_graph_update(merged: RAGState, chunk: dict) -> tuple[str, RAGState]:
    """合并 astream updates 单步，返回 (node_name, merged_state)。"""
    node_name = next(iter(chunk))
    merged.update(chunk[node_name])
    return node_name, merged


async def _astream_rag_graph(
    question: str,
    history: List[BaseMessage],
    *,
    user_roles: Optional[List[str]],
    thread_id: Optional[str],
    conversation_id: Optional[str],
    hitl_approved: bool,
    sink: dict,
) -> AsyncGenerator[str, None]:
    """
    通过 graph.astream(updates + custom) 跑全图，generate 节点逐 token 输出。

    grade 将重试时丢弃本轮已缓冲 token，仅 flush 最终一轮生成内容。
    """
    graph = get_graph()
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    initial = _base_state(question, history, user_roles, thread_id, hitl_approved)

    merged: RAGState = dict(initial)
    token_buffer: list[str] = []
    streamed_any = False

    async for mode, chunk in graph.astream(
        initial,
        config=config,
        stream_mode=["updates", "custom"],
    ):
        if mode == "custom":
            if isinstance(chunk, dict) and chunk.get("type") == "token":
                content = chunk.get("content") or ""
                if content:
                    token_buffer.append(content)
            continue

        node_name, merged = _merge_graph_update(merged, chunk)

        if node_name == "guard" and merged.get("error") == "blocked":
            token_buffer.clear()
            answer = merged.get("answer", "")
            if answer:
                yield answer
                streamed_any = True
        elif node_name == "grade":
            will_retry = (
                merged.get("grade") == "no"
                and merged.get("iterations", 0) < settings.max_iterations
            )
            if will_retry:
                token_buffer.clear()
            else:
                for token in token_buffer:
                    yield token
                    streamed_any = True
                token_buffer.clear()

    if token_buffer:
        for token in token_buffer:
            yield token
            streamed_any = True
        token_buffer.clear()

    if not streamed_any and merged.get("answer"):
        yield merged["answer"]

    sink["state"] = merged
    sink["effective_thread"] = effective_thread


async def ask_stream_async(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    hitl_approved: bool = False,
    use_cache: bool = True,
    stream_chunk_chars: int = 12,
) -> AsyncGenerator[str, None]:
    """
    流式问答：与 ask() 共用压缩、Redis 缓存；未命中时 graph.astream 跑全图。

    generate 节点通过 custom stream 逐 token yield；末尾 __META__ 与 ask() 字段对齐。
    """
    history = compress_chat_history(chat_history or [])
    ck = _cache_key_for_ask(question, user_roles, history, conversation_id)
    t0 = time.perf_counter()

    if use_cache and settings.cache_enabled:
        cached = cache_get(ck)
        if cached:
            cached = dict(cached)
            cached["cached"] = True
            cached.setdefault("latency_ms", 0)
            for chunk in _iter_answer_chunks(cached.get("answer", ""), stream_chunk_chars):
                yield chunk
            yield f"\n\n__META__{json.dumps(_meta_payload(cached), ensure_ascii=False)}"
            return

    sink: dict = {}
    async for token in _astream_rag_graph(
        question,
        history,
        user_roles=user_roles,
        thread_id=thread_id,
        conversation_id=conversation_id,
        hitl_approved=hitl_approved,
        sink=sink,
    ):
        yield token

    merged_state = sink.get("state")
    if not merged_state:
        return

    effective_thread = sink.get("effective_thread") or thread_id or conversation_id or get_request_id()
    result = _result_from_state(
        merged_state,
        conversation_id=conversation_id,
        effective_thread=effective_thread,
    )
    if not result.get("latency_ms"):
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000)

    _maybe_cache_result(ck, result, merged_state, use_cache=use_cache)
    yield f"\n\n__META__{json.dumps(_meta_payload(result), ensure_ascii=False)}"


def ask_stream(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    hitl_approved: bool = False,
    use_cache: bool = True,
    stream_chunk_chars: int = 12,
) -> Generator[str, None, None]:
    """同步包装：供 Streamlit / 同步调用方使用 ask_stream_async。"""
    import asyncio

    async def _collect():
        async for item in ask_stream_async(
            question,
            chat_history,
            user_roles=user_roles,
            thread_id=thread_id,
            conversation_id=conversation_id,
            hitl_approved=hitl_approved,
            use_cache=use_cache,
            stream_chunk_chars=stream_chunk_chars,
        ):
            yield item

    agen = _collect()
    loop = asyncio.new_event_loop()
    try:
        while True:
            try:
                yield loop.run_until_complete(agen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        loop.close()
        asyncio.set_event_loop(None)


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
