"""
agent_service.py — 通用 Agent 用例编排（rag / react 等多模式）

封装 LangGraph 同步/流式问答、HITL 恢复、运行态统计；供 services/api 调用。
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import AsyncGenerator, Callable, Generator, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from loguru import logger

from app.core.config import settings
from app.agent.factory import get_graph, normalize_agent_mode, reset_graph, supported_modes
from app.agent.graphs.rag.state import RagState
from app.core.compression import compress_chat_history
from app.core.streaming import CancelToken, batched_tokens
from app.gateway.request_context import get_request_id, new_request_id
from app.infrastructure.cache.redis_cache import cache_get, cache_key, cache_set
from app.infrastructure.persistence.stream_wal import append_event, begin_stream, finalize_stream


def _base_state(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    hitl_approved: bool = False,
) -> RagState:
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


def _history_signature(chat_history: List[BaseMessage]) -> str:
    """最近 6 条消息的摘要，用于无 conversation_id 时的缓存键（无需先 compress）。"""
    sig = "|".join(f"{type(m).__name__}:{getattr(m, 'content', '')}" for m in chat_history[-6:])
    return hashlib.sha256(sig.encode()).hexdigest()[:16]


def _cache_key_for_ask(
    question: str,
    user_roles: Optional[List[str]],
    chat_history: Optional[List[BaseMessage]] = None,
    conversation_id: Optional[str] = None,
    agent_mode: Optional[str] = None,
) -> str:
    """多轮会话下缓存键需含会话、模式或历史摘要，避免误命中。"""
    payload: dict = {
        "q": question,
        "roles": user_roles,
        "mode": normalize_agent_mode(agent_mode),
    }
    if conversation_id:
        payload["conv"] = conversation_id
    elif chat_history:
        payload["hist"] = _history_signature(chat_history)
    return cache_key("ask", payload)


def get_cached_ask(
    question: str,
    *,
    user_roles: Optional[List[str]] = None,
    conversation_id: Optional[str] = None,
    chat_history: Optional[List[BaseMessage]] = None,
    use_cache: bool = True,
    agent_mode: Optional[str] = None,
) -> Optional[dict]:
    """
    仅查 Redis 答案缓存，不压缩历史、不跑 LangGraph。

    有 conversation_id 时无需 chat_history；供 api 层在加载 PG 历史之前短路命中路径。
    """
    if not use_cache or not settings.cache_enabled:
        return None
    ck = _cache_key_for_ask(question, user_roles, chat_history, conversation_id, agent_mode)
    cached = cache_get(ck)
    if not cached:
        return None
    cached = dict(cached)
    cached["cached"] = True
    return cached


def _resolve_history(
    history: Optional[List[BaseMessage]],
    history_loader: Optional[Callable[[], List[BaseMessage]]],
) -> List[BaseMessage]:
    """解析聊天历史：优先显式 history，否则调用 loader。"""
    if history is not None:
        return history
    if history_loader is not None:
        return history_loader()
    return []


def _result_from_state(
    state: RagState,
    *,
    conversation_id: Optional[str],
    effective_thread: str,
    cached: bool = False,
) -> dict:
    """将 RAG 图状态整理为 API 统一结果字典。"""
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
) -> tuple[RagState, str]:
    """同步调用 RAG 图并返回最终状态与有效 thread_id。"""
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    state = get_graph("rag").invoke(
        _base_state(question, history, user_roles, thread_id, hitl_approved),
        config=config,
    )
    return state, effective_thread


def _extract_ai_answer(messages: list) -> str:
    """从消息列表末尾提取最近一条 AI 回答文本。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if content:
                return content if isinstance(content, str) else str(content)
    return ""


def _invoke_react_graph(
    question: str,
    history: List[BaseMessage],
    *,
    thread_id: Optional[str],
    conversation_id: Optional[str],
) -> tuple[dict, str]:
    """同步调用 ReAct 图并整理为统一结果字典。"""
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    messages = list(history) + [HumanMessage(content=question)]
    t0 = time.perf_counter()
    result = get_graph("react").invoke({"messages": messages}, config=config)
    answer = _extract_ai_answer(result.get("messages", []))
    return {
        "answer": answer,
        "sources": [],
        "latency_ms": round((time.perf_counter() - t0) * 1000),
        "iterations": 1,
        "grade": "n/a",
        "error": None,
        "disclaimer": "",
        "conflicts": "",
        "request_id": get_request_id() or new_request_id(),
        "hitl_pending": False,
        "agent_mode": "react",
    }, effective_thread


def _maybe_cache_result(ck: str, result: dict, state: RagState, *, use_cache: bool) -> None:
    """在无 HITL/错误时将结果写入缓存。"""
    if use_cache and not result.get("hitl_pending") and not state.get("error"):
        cache_set(ck, result)


def _meta_payload(result: dict) -> dict:
    """从结果中抽取流式 __META__ 载荷字段。"""
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
    """按固定字符数切分答案文本，供流式输出。"""
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
    agent_mode: Optional[str] = None,
) -> dict:
    """同步问答：按 agent_mode 路由到 rag 或 react 图。"""
    mode = normalize_agent_mode(agent_mode)
    ck = _cache_key_for_ask(question, user_roles, chat_history, conversation_id, mode)
    cached = get_cached_ask(
        question,
        user_roles=user_roles,
        conversation_id=conversation_id,
        chat_history=chat_history,
        use_cache=use_cache,
        agent_mode=mode,
    )
    if cached:
        return cached

    history = compress_chat_history(chat_history or [])

    if mode == "react":
        react_result, effective_thread = _invoke_react_graph(
            question,
            history,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )
        react_result["thread_id"] = effective_thread
        react_result["conversation_id"] = conversation_id
        react_result["agent_mode"] = mode
        if use_cache and react_result.get("answer"):
            cache_set(ck, react_result)
        return react_result

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
    result["agent_mode"] = mode
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
    graph = get_graph("rag")
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


def _merge_graph_update(merged: RagState, chunk: dict) -> tuple[str, RagState]:
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
    cancel: Optional[CancelToken] = None,
) -> AsyncGenerator[str, None]:
    """
    通过 graph.astream(updates + custom) 跑全图，generate 节点逐 token 输出。

    grade 将重试时丢弃本轮已缓冲 token，仅 flush 最终一轮生成内容。
    """
    graph = get_graph("rag")
    effective_thread = thread_id or conversation_id or get_request_id()
    config = {"configurable": {"thread_id": effective_thread}}
    initial = _base_state(question, history, user_roles, thread_id, hitl_approved)

    merged: RagState = dict(initial)
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
                    if cancel and cancel.is_cancelled:
                        break
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


async def _produce_stream_to_wal(
    *,
    stream_id: str,
    question: str,
    history: Optional[List[BaseMessage]],
    history_loader: Optional[Callable[[], List[BaseMessage]]],
    user_roles: Optional[List[str]],
    thread_id: Optional[str],
    conversation_id: Optional[str],
    hitl_approved: bool,
    use_cache: bool,
    cancel: CancelToken,
    agent_mode: Optional[str] = None,
) -> None:
    """
    后台任务：跑完 ask_stream_async 逻辑并将 token/meta 写入 WAL。

    与 HTTP 连接解耦，支持断线后续推。
    """
    try:
        async for batch in batched_tokens(
            _raw_token_stream(
                question,
                history,
                history_loader=history_loader,
                user_roles=user_roles,
                thread_id=thread_id,
                conversation_id=conversation_id,
                hitl_approved=hitl_approved,
                use_cache=use_cache,
                cancel=cancel,
                agent_mode=agent_mode,
            ),
            cancel=cancel,
        ):
            if batch.startswith("\n\n__META__"):
                meta = json.loads(batch.replace("\n\n__META__", ""))
                append_event(stream_id, "meta", meta)
            else:
                append_event(stream_id, "token", {"token": batch})
        append_event(stream_id, "done", {})
        finalize_stream(stream_id, status="complete")
    except asyncio.CancelledError:
        finalize_stream(stream_id, status="cancelled")
        raise
    except Exception as e:
        logger.error(f"Stream WAL produce failed: {e}")
        append_event(stream_id, "error", {"message": str(e)})
        finalize_stream(stream_id, status="error", error=str(e))


async def _raw_token_stream(
    question: str,
    history: Optional[List[BaseMessage]] = None,
    *,
    history_loader: Optional[Callable[[], List[BaseMessage]]] = None,
    user_roles: Optional[List[str]],
    thread_id: Optional[str],
    conversation_id: Optional[str],
    hitl_approved: bool,
    use_cache: bool,
    cancel: Optional[CancelToken],
    agent_mode: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """内部 token 源（含 cache 命中路径），供 WAL 生产者与 ask_stream_async 共用。"""
    mode = normalize_agent_mode(agent_mode)
    ck = _cache_key_for_ask(question, user_roles, history, conversation_id, mode)
    t0 = time.perf_counter()

    cached = get_cached_ask(
        question,
        user_roles=user_roles,
        conversation_id=conversation_id,
        chat_history=history,
        use_cache=use_cache,
        agent_mode=mode,
    )
    if cached:
        cached.setdefault("latency_ms", 0)
        for chunk in _iter_answer_chunks(cached.get("answer", ""), settings.stream_flush_chars):
            if cancel and cancel.is_cancelled:
                return
            yield chunk
        yield f"\n\n__META__{json.dumps(_meta_payload(cached), ensure_ascii=False)}"
        return

    raw_history = _resolve_history(history, history_loader)
    history = compress_chat_history(raw_history)

    if mode == "react":
        react_result, effective_thread = _invoke_react_graph(
            question,
            history,
            thread_id=thread_id,
            conversation_id=conversation_id,
        )
        react_result["thread_id"] = effective_thread
        react_result["conversation_id"] = conversation_id
        react_result["agent_mode"] = mode
        for chunk in _iter_answer_chunks(react_result.get("answer", ""), settings.stream_flush_chars):
            if cancel and cancel.is_cancelled:
                return
            yield chunk
        if use_cache and react_result.get("answer"):
            cache_set(ck, react_result)
        yield f"\n\n__META__{json.dumps(_meta_payload(react_result), ensure_ascii=False)}"
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
        cancel=cancel,
    ):
        if cancel and cancel.is_cancelled:
            break
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


# 进程内后台 WAL 生产任务 registry（stream_id -> task）
_active_stream_tasks: dict[str, asyncio.Task] = {}


def register_stream_task(stream_id: str, task: asyncio.Task) -> None:
    """注册后台流式任务，完成后自动从 registry 移除。"""
    _active_stream_tasks[stream_id] = task
    task.add_done_callback(lambda _t: _active_stream_tasks.pop(stream_id, None))


def get_stream_task(stream_id: str) -> Optional[asyncio.Task]:
    """按 stream_id 查询进程内后台流式任务。"""
    return _active_stream_tasks.get(stream_id)


async def start_wal_stream_producer(
    *,
    stream_id: str,
    conversation_id: str,
    question: str,
    history: Optional[List[BaseMessage]] = None,
    history_loader: Optional[Callable[[], List[BaseMessage]]] = None,
    user_roles: Optional[List[str]],
    hitl_approved: bool,
    use_cache: bool,
    agent_mode: Optional[str] = None,
) -> CancelToken:
    """启动后台 WAL 生产者；若已有同 stream_id 任务在跑则复用。"""
    existing = get_stream_task(stream_id)
    if existing and not existing.done():
        return CancelToken()  # resume 侧只读 WAL

    begin_stream(
        stream_id,
        conversation_id=conversation_id,
        request_id=stream_id,
        message=question,
    )
    cancel = CancelToken()
    task = asyncio.create_task(
        _produce_stream_to_wal(
            stream_id=stream_id,
            question=question,
            history=history,
            history_loader=history_loader,
            user_roles=user_roles,
            thread_id=conversation_id,
            conversation_id=conversation_id,
            hitl_approved=hitl_approved,
            use_cache=use_cache,
            cancel=cancel,
            agent_mode=agent_mode,
        )
    )
    register_stream_task(stream_id, task)
    return cancel


async def ask_stream_async(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    history_loader: Optional[Callable[[], List[BaseMessage]]] = None,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    hitl_approved: bool = False,
    use_cache: bool = True,
    stream_chunk_chars: Optional[int] = None,
    cancel: Optional[CancelToken] = None,
    agent_mode: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    流式问答：先查 Redis；未命中再加载/压缩历史并 graph.astream 跑全图。

    默认按 settings.stream_flush_chars / stream_flush_interval_ms 节流 batch。
    """
    flush_chars = stream_chunk_chars if stream_chunk_chars is not None else settings.stream_flush_chars
    async for batch in batched_tokens(
        _raw_token_stream(
            question,
            chat_history,
            history_loader=history_loader,
            user_roles=user_roles,
            thread_id=thread_id,
            conversation_id=conversation_id,
            hitl_approved=hitl_approved,
            use_cache=use_cache,
            cancel=cancel,
            agent_mode=agent_mode,
        ),
        flush_chars=flush_chars,
        cancel=cancel,
    ):
        yield batch


def ask_stream(
    question: str,
    chat_history: Optional[List[BaseMessage]] = None,
    *,
    history_loader: Optional[Callable[[], List[BaseMessage]]] = None,
    user_roles: Optional[List[str]] = None,
    thread_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    hitl_approved: bool = False,
    use_cache: bool = True,
    stream_chunk_chars: int = 12,
    agent_mode: Optional[str] = None,
) -> Generator[str, None, None]:
    """同步包装：供 Streamlit / 同步调用方使用 ask_stream_async。"""
    import asyncio

    async def _collect():
        """桥接 ask_stream_async，供同步 ask_stream 逐项取出。"""
        async for item in ask_stream_async(
            question,
            chat_history,
            history_loader=history_loader,
            user_roles=user_roles,
            thread_id=thread_id,
            conversation_id=conversation_id,
            hitl_approved=hitl_approved,
            use_cache=use_cache,
            stream_chunk_chars=stream_chunk_chars,
            agent_mode=agent_mode,
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
    """应用启动预热（委托 warmup_service，保持旧入口兼容）。"""
    from app.services.warmup_service import warmup

    warmup()


def get_stats() -> dict:
    """
    返回当前检索层与熔断器运行态，便于 /health 或监控面板展示。
    """
    from app.knowledge.knowledge_graph import get_kg
    from app.knowledge.retriever import _chunks, get_vectorstore
    from app.core.circuit_breaker import llm_breaker, embed_breaker

    try:
        count = get_vectorstore()._collection.count()
    except Exception:
        count = 0
    from app.infrastructure.providers.factory import routing_status
    return {
        "documents_indexed": count,
        "bm25_chunks": len(_chunks),
        "kg_triples": len(get_kg().triples),
        "retrieval_mode": settings.retrieval_mode,
        "default_agent_mode": settings.default_agent_mode,
        "supported_agent_modes": supported_modes(),
        "llm_provider": settings.llm_provider,
        "model_routing": routing_status(),
        "stream_resume_enabled": settings.stream_resume_enabled,
        "circuit_breakers": [llm_breaker.status(), embed_breaker.status()],
    }
