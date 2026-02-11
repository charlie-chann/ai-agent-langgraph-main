"""
agent.py — ReAct 多工具 Agent 核心逻辑（LangGraph）

【职责】
1. 用 create_react_agent 组装 LLM + 6 个工具，实现「思考→行动→观察」循环
2. 提供 run / run_with_memory / run_stream 等对外 API
3. 管理 Agent 单例与对话记忆读写

【设计原因】
1. LangGraph prebuilt ReAct：比手写 ToolNode 更简洁，社区标准方案
2. 记忆与 Agent 分离：memory.py 管存储，agent.py 只管注入与保存
3. 同步/流式两套 API：Streamlit 用同步，FastAPI SSE 用流式
"""
from __future__ import annotations

import json
import time
from typing import Generator, List, Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent
from loguru import logger

from config import settings, OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.search_tool import web_search
from tools.calculator_tool import calculator
from tools.file_tool import file_read, file_write, file_list
from tools.datetime_tool import get_datetime
from memory import get_memory_store, MemoryStore


# Agent 可调用的全部工具列表，顺序不影响行为
ALL_TOOLS = [web_search, calculator, file_read, file_write, file_list, get_datetime]


# ── LLM 工厂 ──────────────────────────────────────────────────────────────────
def _llm(streaming: bool = False) -> ChatOllama:
    """
    创建 Ollama Chat 模型实例。

    参数:
        streaming: True 时启用 token 流式输出（run_stream 使用）
    """
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        streaming=streaming,
    )


# ── Agent 单例缓存 ────────────────────────────────────────────────────────────
_agent = None


def get_agent():
    """
    获取或创建 ReAct Agent 单例。

    说明:
        首次调用时 create_react_agent，后续复用同一实例，避免重复初始化 LLM。
    """
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            model=_llm(),
            tools=ALL_TOOLS,
        )
        logger.info("Agent initialized")
    return _agent


def reset_agent():
    """重置 Agent 单例，单元测试或切换模型后调用。"""
    global _agent
    _agent = None
    logger.info("Agent reset")


# ── 运行入口（无记忆）────────────────────────────────────────────────────────

def run(question: str, chat_history: Optional[List[BaseMessage]] = None) -> dict:
    """
    同步运行 Agent，不持久化对话记忆。

    参数:
        question: 用户问题
        chat_history: 可选的历史消息，手动传入时使用

    返回:
        dict: answer, steps（工具调用链）, latency_ms, tool_calls
    """
    t0 = time.perf_counter()

    agent = get_agent()

    # 组装消息列表：历史 + 当前问题
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=question))

    # invoke 一次性跑完 ReAct 循环，stream_mode="values" 返回最终 state
    result = agent.invoke({"messages": messages}, stream_mode="values")

    latency_ms = round((time.perf_counter() - t0) * 1000)

    # 从返回的 messages 中提取 tool 类型消息，构建 steps 供 UI 展示
    steps = []
    result_messages = result.get("messages", [])
    for msg in result_messages:
        if hasattr(msg, "type") and msg.type == "tool":
            steps.append({
                "tool": getattr(msg, "name", "unknown"),
                "input": str(getattr(msg, "tool_input", ""))[:200],
                "output": str(getattr(msg, "content", ""))[:500],
            })

    # 倒序找最后一条 AI 消息作为最终答案
    answer = ""
    for msg in reversed(result_messages):
        if hasattr(msg, "type") and msg.type == "ai":
            answer = getattr(msg, "content", "")
            break

    return {
        "answer": answer,
        "steps": steps,
        "latency_ms": latency_ms,
        "tool_calls": len(steps),
    }


def run_with_memory(question: str, session_id: str = "default") -> dict:
    """
    带自动对话记忆的运行（推荐用于多轮对话）。

    流程:
        1. 从 MemoryStore 加载最近 20 条历史
        2. 注入 Agent 上下文并执行
        3. 将本轮 user/ai 消息写回记忆

    参数:
        session_id: 会话 ID，相同 ID 共享记忆
    """
    t0 = time.perf_counter()

    agent = get_agent()
    memory = get_memory_store().get_or_create_session(session_id)

    chat_history = memory.get_langchain_messages(limit=20)

    messages = chat_history.copy()
    messages.append(HumanMessage(content=question))

    logger.info(f"[Memory] Session {session_id}: loaded {len(chat_history)} history messages")

    result = agent.invoke({"messages": messages}, stream_mode="values")

    latency_ms = round((time.perf_counter() - t0) * 1000)

    steps = []
    result_messages = result.get("messages", [])

    for msg in result_messages:
        if hasattr(msg, "type"):
            if msg.type == "tool":
                steps.append({
                    "tool": getattr(msg, "name", "unknown"),
                    "input": str(getattr(msg, "tool_input", ""))[:200],
                    "output": str(getattr(msg, "content", ""))[:500],
                })

    answer = ""
    for msg in reversed(result_messages):
        if hasattr(msg, "type") and msg.type == "ai":
            answer = getattr(msg, "content", "")
            break

    # 持久化本轮问答到记忆
    memory.add_user_message(question)
    memory.add_ai_message(answer)

    logger.info(f"[Memory] Session {session_id}: saved exchange, total messages: {len(memory.messages)}")

    return {
        "answer": answer,
        "steps": steps,
        "latency_ms": latency_ms,
        "tool_calls": len(steps),
        "session_id": session_id,
        "message_count": len(memory.messages),
    }


def run_stream(question: str, chat_history: Optional[List[BaseMessage]] = None) -> Generator[dict, None, None]:
    """
    流式运行（无记忆），逐 token / 工具事件 yield。

    事件类型:
        {"type": "token", "content": "..."}   — LLM 输出片段
        {"type": "tool_end", "tool": ..., "output": ...} — 工具执行完成
        {"type": "done", "latency_ms": ..., "tool_calls": ...} — 结束
    """
    t0 = time.perf_counter()
    tool_calls = 0

    agent = get_agent()

    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=question))

    # stream_mode="updates"：每个节点完成时推送一次
    for event in agent.stream({"messages": messages}, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "agent":
                # Agent 节点：提取 AI 生成的 token
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = getattr(msg, "content", "")
                        if content:
                            yield {"type": "token", "content": content}
            elif node_name.startswith("tools_"):
                # 工具节点：推送工具名与输出摘要
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "tool":
                        tool_calls += 1
                        yield {
                            "type": "tool_end",
                            "tool": getattr(msg, "name", "unknown"),
                            "output": str(getattr(msg, "content", ""))[:300],
                        }

    latency_ms = round((time.perf_counter() - t0) * 1000)
    yield {
        "type": "done",
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
    }


def run_stream_with_memory(question: str, session_id: str = "default") -> Generator[dict, None, None]:
    """
    流式运行 + 记忆：边输出边累积 answer_content，结束后写入 MemoryStore。
    """
    t0 = time.perf_counter()
    tool_calls = 0

    agent = get_agent()
    memory = get_memory_store().get_or_create_session(session_id)

    chat_history = memory.get_langchain_messages(limit=20)
    messages = chat_history.copy()
    messages.append(HumanMessage(content=question))

    logger.info(f"[Memory Stream] Session {session_id}: loaded {len(chat_history)} messages")

    answer_content = ""

    for event in agent.stream({"messages": messages}, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "agent":
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = getattr(msg, "content", "")
                        if content:
                            answer_content += content
                            yield {"type": "token", "content": content}
            elif node_name.startswith("tools_"):
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "tool":
                        tool_calls += 1
                        yield {
                            "type": "tool_end",
                            "tool": getattr(msg, "name", "unknown"),
                            "output": str(getattr(msg, "content", ""))[:300],
                        }

    memory.add_user_message(question)
    memory.add_ai_message(answer_content)

    latency_ms = round((time.perf_counter() - t0) * 1000)
    yield {
        "type": "done",
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
        "session_id": session_id,
    }


# ── 记忆管理 API ──────────────────────────────────────────────────────────────

def get_memory_stats(session_id: Optional[str] = None) -> dict:
    """查询单个 session 或全部 session 的记忆统计。"""
    store = get_memory_store()
    if session_id:
        session = store.get_session(session_id)
        if session:
            return {
                "session_id": session_id,
                "message_count": len(session.messages),
                "created_at": session.created_at,
                "last_updated": session.last_updated,
                "messages": session.messages,
            }
        return {"error": f"Session {session_id} not found"}
    return store.get_stats()


def clear_memory(session_id: Optional[str] = None) -> dict:
    """清空指定 session 或全部 session 的记忆。"""
    store = get_memory_store()
    if session_id:
        store.clear_session(session_id)
        return {"message": f"Cleared session {session_id}"}
    else:
        for sid in store.get_all_sessions():
            store.clear_session(sid)
        return {"message": "Cleared all sessions"}


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """返回 Agent 运行时统计（工具数、模型名等），供 /stats 接口使用。"""
    return {
        "num_tools": len(ALL_TOOLS),
        "tool_names": [t.name for t in ALL_TOOLS],
        "model": DEFAULT_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
    }
