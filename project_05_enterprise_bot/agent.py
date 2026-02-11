# agent.py — Enterprise Bot Agent with memory + RBAC
from __future__ import annotations

import time
from typing import List, Generator

from langchain_community.chat_models import ChatOllama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, MAX_HISTORY_MESSAGES
from prompts.bot_prompts import bot_prompt
from tools.ticket_tool import create_ticket, list_tickets, close_ticket
from tools.kb_tool import search_kb
from tools.notification_tool import send_notification, get_notifications
from tools.rbac import get_user_role, check_permission, get_allowed_tools

ALL_TOOLS = [create_ticket, list_tickets, close_ticket, search_kb, send_notification, get_notifications]
TOOL_MAP = {t.name: t for t in ALL_TOOLS}

# Per-user conversation memory (in-memory)
_MEMORY: dict[str, list[BaseMessage]] = {}


def get_history(username: str) -> list[BaseMessage]:
    return _MEMORY.get(username, [])[-MAX_HISTORY_MESSAGES:]


def add_to_history(username: str, human_msg: str, ai_msg: str) -> None:
    hist = _MEMORY.setdefault(username, [])
    hist.append(HumanMessage(content=human_msg))
    hist.append(AIMessage(content=ai_msg))
    # Trim to prevent unbounded growth
    _MEMORY[username] = hist[-MAX_HISTORY_MESSAGES * 2:]


def clear_history(username: str) -> None:
    _MEMORY.pop(username, None)


def _get_user_tools(username: str) -> list:
    """Return tools filtered by user's RBAC permissions."""
    allowed = get_allowed_tools(username)
    return [t for t in ALL_TOOLS if t.name in allowed]


def _llm() -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )


def chat(username: str, message: str) -> dict:
    """Process a user message. Returns answer + metadata."""
    t0 = time.perf_counter()
    role = get_user_role(username)
    user_tools = _get_user_tools(username)
    history = get_history(username)

    llm = _llm()
    agent = create_react_agent(
        llm=llm,
        tools=user_tools,
        prompt=bot_prompt,
    )
    executor = AgentExecutor(
        agent=agent,
        tools=user_tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=6,
        return_intermediate_steps=True,
    )

    try:
        result = executor.invoke({
            "input": message,
            "username": username,
            "role": role,
            "allowed_actions": ", ".join(get_allowed_tools(username)),
            "chat_history": history,
        })
        answer = result.get("output", "")
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
