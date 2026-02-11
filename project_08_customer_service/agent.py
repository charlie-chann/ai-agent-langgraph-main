# agent.py — 客服全链路 Agent（LangChain ReAct + 会话记忆）
"""
客服 Agent 核心逻辑：
- 基于 LangChain ReAct 架构
- 内置会话记忆（用户级别的多轮对话）
- 情感检测 + 自动升级触发
- 工具集：知识库搜索、工单管理、情感分析、订单查询
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from loguru import logger

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    AGENT_MAX_ITERATIONS, COMPANY_NAME,
    ESCALATION_SENTIMENT_THRESHOLD,
)
from prompts.cs_prompts import CS_REACT_TEMPLATE
from tools.kb_tool import search_kb, list_kb_categories
from tools.ticket_tool import create_ticket, get_ticket, list_user_tickets, update_ticket_status, escalate_ticket
from tools.sentiment_tool import analyse_sentiment, classify_intent
from tools.order_tool import query_order_status, list_user_orders

# ── 工具集 ─────────────────────────────────────────────────────────────────────
ALL_TOOLS = [
    # 情感与意图判断
    analyse_sentiment,
    classify_intent,
    # 知识库
    search_kb,
    list_kb_categories,
    # 工单管理
    create_ticket,
    get_ticket,
    list_user_tickets,
    update_ticket_status,
    escalate_ticket,
    # 订单查询
    query_order_status,
    list_user_orders,
]

_TOOL_NAMES = ", ".join(t.name for t in ALL_TOOLS)
_TOOL_DESCS = "\n".join(f"{t.name}: {t.description}" for t in ALL_TOOLS)

# ── 会话记忆（用户级别） ────────────────────────────────────────────────────────
# {user_id: [{"role": "user"|"assistant", "content": "..."}]}
_SESSION_MEMORY: dict[str, list[dict]] = {}
_MAX_HISTORY = 10  # 每用户保留最近10轮对话


def get_session_history(user_id: str) -> list[dict]:
    """获取用户的对话历史。"""
    return _SESSION_MEMORY.get(user_id, [])


def add_to_session(user_id: str, role: str, content: str) -> None:
    """将消息添加到用户的会话记忆中。"""
    if user_id not in _SESSION_MEMORY:
        _SESSION_MEMORY[user_id] = []
    _SESSION_MEMORY[user_id].append({"role": role, "content": content})
    # 只保留最近N轮
    if len(_SESSION_MEMORY[user_id]) > _MAX_HISTORY * 2:
        _SESSION_MEMORY[user_id] = _SESSION_MEMORY[user_id][-_MAX_HISTORY * 2:]


def clear_session(user_id: str) -> None:
    """清除用户的会话历史。"""
    _SESSION_MEMORY.pop(user_id, None)


def _build_context_prompt(user_id: str, message: str) -> str:
    """
    将历史对话注入到当前用户消息，让模型感知上下文。
    """
    history = get_session_history(user_id)
    if not history:
        return message

    history_text = "\n".join(
        f"{'用户' if h['role'] == 'user' else '客服'}: {h['content']}"
        for h in history[-6:]  # 只附带最近3轮
    )
    return f"【历史对话】\n{history_text}\n\n【当前问题】\n{message}"


def build_agent(model: str | None = None) -> AgentExecutor:
    """构建客服 ReAct AgentExecutor。"""
    llm = Ollama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )
    prompt = PromptTemplate.from_template(
        CS_REACT_TEMPLATE.format(company_name=COMPANY_NAME).replace(
            "{tools}", _TOOL_DESCS
        ).replace("{tool_names}", _TOOL_NAMES)
    )
    agent = create_react_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=AGENT_MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def run_agent(
    user_message: str,
    user_id: str = "anonymous",
    model: str | None = None,
) -> dict:
    """
    运行客服Agent，返回完整结果。
    自动进行情感分析，检测到高负面情绪时在结果中标记。
    """
    # 预检测情感（不消耗Agent迭代次数）
    sentiment_raw = analyse_sentiment.invoke(user_message)
    import json
    sentiment = json.loads(sentiment_raw)
    needs_escalation = sentiment.get("needs_escalation", False)

    # 构建含历史的完整输入
    full_input = _build_context_prompt(user_id, user_message)

    executor = build_agent(model)
    logger.info(f"[cs_agent] user={user_id!r} sentiment={sentiment.get('score')} escalate={needs_escalation}")

    result = executor.invoke({"input": full_input})
    output = result.get("output", "")

    # 更新会话记忆
    add_to_session(user_id, "user", user_message)
    add_to_session(user_id, "assistant", output)

    return {
        "output": output,
        "user_id": user_id,
        "sentiment": sentiment,
        "needs_escalation": needs_escalation,
        "steps": [
            {"tool": a.tool, "input": str(a.tool_input)[:200], "output": str(o)[:300]}
            for a, o in result.get("intermediate_steps", [])
        ],
    }
