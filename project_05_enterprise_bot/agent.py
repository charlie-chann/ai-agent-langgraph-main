"""
agent.py — 企业机器人 Agent 核心编排模块

【职责】
组装 LangChain ReAct Agent：按用户 RBAC 过滤工具、注入对话历史、
调用 Ollama LLM 执行推理，并维护 per-user 内存会话。

【设计原因】
将「模型 + 工具 + 提示词 + 记忆」收敛于单一 chat() 入口，供 Streamlit UI
与 FastAPI 共用；RBAC 在工具列表层过滤，避免 Agent 调用无权限工具。
"""
from __future__ import annotations

import time
from typing import List, Generator

from langchain_ollama import ChatOllama
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, MAX_HISTORY_MESSAGES
from prompts.bot_prompts import build_bot_prompt
from tools.ticket_tool import create_ticket, list_tickets, close_ticket
from tools.kb_tool import search_kb
from tools.notification_tool import send_notification, get_notifications
from tools.rbac import get_user_role, check_permission, get_allowed_tools

# 全量工具注册表 — 实际下发给 Agent 的子集由 RBAC 决定
ALL_TOOLS = [create_ticket, list_tickets, close_ticket, search_kb, send_notification, get_notifications]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# 按 username 隔离的对话记忆（进程内字典，重启后丢失）
_MEMORY: dict[str, list[BaseMessage]] = {}


def get_history(username: str) -> list[BaseMessage]:
    """
    获取指定用户最近的对话历史消息列表。

    Args:
        username: 用户账号

    Returns:
        截断至 MAX_HISTORY_MESSAGES 条后的 BaseMessage 列表
    """
    return _MEMORY.get(username, [])[-MAX_HISTORY_MESSAGES:]


def add_to_history(username: str, human_msg: str, ai_msg: str) -> None:
    """
    将一轮 Human/AI 消息追加到用户历史中，并裁剪超长部分。

    Args:
        username: 用户账号
        human_msg: 用户本轮输入文本
        ai_msg: 助手本轮回复文本
    """
    hist = _MEMORY.setdefault(username, [])
    hist.append(HumanMessage(content=human_msg))
    hist.append(AIMessage(content=ai_msg))
    # 保留最近 MAX_HISTORY_MESSAGES*2 条（Human+AI 成对），防止内存无限增长
    _MEMORY[username] = hist[-MAX_HISTORY_MESSAGES * 2:]


def clear_history(username: str) -> None:
    """
    清空指定用户的全部对话记忆。

    Args:
        username: 待清除历史的用户账号
    """
    _MEMORY.pop(username, None)


def _build_input_with_history(username: str, message: str) -> str:
    """将最近对话历史拼入当前输入，供 ReAct Agent 感知上下文。"""
    history = get_history(username)
    if not history:
        return message

    lines = []
    for msg in history[-6:]:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        lines.append(f"{role}: {msg.content}")
    return "【Chat history】\n" + "\n".join(lines) + f"\n\n【Current question】\n{message}"


def _get_user_tools(username: str) -> list:
    """
    根据 RBAC 权限过滤当前用户可用的 LangChain 工具列表。

    Args:
        username: 当前用户账号

    Returns:
        该用户有权调用的 StructuredTool 实例列表
    """
    allowed = get_allowed_tools(username)
    return [t for t in ALL_TOOLS if t.name in allowed]


def _llm() -> ChatOllama:
    """
    构造 ChatOllama 实例，读取 config 中的模型与温度参数。

    Returns:
        配置完毕的 ChatOllama 客户端
    """
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )


def chat(username: str, message: str) -> dict:
    """
    处理单轮用户消息，执行 ReAct Agent 并返回结构化结果。

    Args:
        username: 当前登录用户，用于 RBAC 与记忆隔离
        message: 用户自然语言输入

    Returns:
        包含 answer、role、steps、latency_ms 等字段的字典
    """
    t0 = time.perf_counter()
    role = get_user_role(username)
    user_tools = _get_user_tools(username)

    llm = _llm()
    # 创建 ReAct 风格 Agent：Thought → Action → Observation 循环
    agent = create_react_agent(
        llm=llm,
        tools=user_tools,
        prompt=build_bot_prompt(),
    )
    executor = AgentExecutor(
        agent=agent,
        tools=user_tools,
        verbose=True,
        handle_parsing_errors=True,  # LLM 输出格式异常时自动重试而非崩溃
        max_iterations=6,            # 限制工具调用轮数，控制延迟与成本
        return_intermediate_steps=True,
    )

    try:
        result = executor.invoke({
            "input": _build_input_with_history(username, message),
            "username": username,
            "role": role,
            "allowed_actions": ", ".join(get_allowed_tools(username)),
        })
        answer = result.get("output", "")
        # 提取中间步骤供 UI/API 展示工具调用链路
        steps = [
            {"tool": a.tool, "input": a.tool_input, "output": str(o)[:300]}
            for a, o in result.get("intermediate_steps", [])
        ]
    except Exception as e:
        logger.error(f"[agent] error for {username}: {e}")
        answer = f"I encountered an error processing your request. Please try again or contact IT."
        steps = []

    add_to_history(username, message, answer)
    latency_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "answer": answer,
        "username": username,
        "role": role,
        "steps": steps,
        "latency_ms": latency_ms,
        "history_length": len(_MEMORY.get(username, [])),
    }
