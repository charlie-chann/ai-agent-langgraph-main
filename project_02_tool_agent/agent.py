# agent.py — ReAct Agent with memory (LangGraph) v2.1
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


# All available tools
ALL_TOOLS = [web_search, calculator, file_read, file_write, file_list, get_datetime]


# ── LLM Factory ────────────────────────────────────────────────────────────────
def _llm(streaming: bool = False) -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        streaming=streaming,
    )


# ── Global Agent Cache ────────────────────────────────────────────────────────
_agent = None


def get_agent():
    """Get or create the agent singleton."""
    global _agent
    if _agent is None:
        _agent = create_react_agent(
            model=_llm(),
            tools=ALL_TOOLS,
        )
        logger.info("Agent initialized")
    return _agent


def reset_agent():
    """Reset agent (useful for testing)."""
    global _agent
    _agent = None
    logger.info("Agent reset")


# ── Run Functions ─────────────────────────────────────────────────────────────

def run(question: str, chat_history: Optional[List[BaseMessage]] = None) -> dict:
    """Non-streaming agent run without memory."""
    t0 = time.perf_counter()
    
    agent = get_agent()
    
    # Build messages without memory
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=question))
    
    # Run agent
    result = agent.invoke({"messages": messages}, stream_mode="values")
    
    latency_ms = round((time.perf_counter() - t0) * 1000)
    
    # Extract tool calls
    steps = []
    result_messages = result.get("messages", [])
    for msg in result_messages:
        if hasattr(msg, "type") and msg.type == "tool":
            steps.append({
                "tool": getattr(msg, "name", "unknown"),
                "input": str(getattr(msg, "tool_input", ""))[:200],
                "output": str(getattr(msg, "content", ""))[:500],
            })
    
    # Final answer
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
    Run agent WITH automatic conversation memory.
    
    This is the recommended way to run the agent for multi-turn conversations.
    The agent automatically:
    1. Loads previous conversation history
    2. Includes it in the context
    3. Saves the new exchange to history
    
    Args:
        question: User's question
        session_id: Unique session identifier (e.g., user ID, conversation ID)
    
    Returns:
        dict with answer, steps, latency_ms, tool_calls, and session_id
    """
    t0 = time.perf_counter()
    
    agent = get_agent()
    memory = get_memory_store().get_or_create_session(session_id)
    
    # Load chat history
    chat_history = memory.get_langchain_messages(limit=20)
    
    # Add current question
    messages = chat_history.copy()
    messages.append(HumanMessage(content=question))
    
    logger.info(f"[Memory] Session {session_id}: loaded {len(chat_history)} history messages")
    
    # Run agent
    result = agent.invoke({"messages": messages}, stream_mode="values")
    
    latency_ms = round((time.perf_counter() - t0) * 1000)
    
    # Extract tool calls and save to memory
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
    
    # Get answer
    answer = ""
    for msg in reversed(result_messages):
        if hasattr(msg, "type") and msg.type == "ai":
            answer = getattr(msg, "content", "")
            break
    
    # Save to memory
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
    """Streaming version without memory."""
    t0 = time.perf_counter()
    tool_calls = 0
    
    agent = get_agent()
    
    messages = []
    if chat_history:
        messages.extend(chat_history)
    messages.append(HumanMessage(content=question))
    
    for event in agent.stream({"messages": messages}, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "agent":
                msgs = node_output.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "ai":
                        content = getattr(msg, "content", "")
                        if content:
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
    
    latency_ms = round((time.perf_counter() - t0) * 1000)
    yield {
        "type": "done",
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
    }


def run_stream_with_memory(question: str, session_id: str = "default") -> Generator[dict, None, None]:
    """
    Streaming version WITH memory.
    
    Same as run_with_memory but yields tokens in real-time.
    """
    t0 = time.perf_counter()
    tool_calls = 0
    
    agent = get_agent()
    memory = get_memory_store().get_or_create_session(session_id)
    
    # Load history
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
    
    # Save to memory
    memory.add_user_message(question)
    memory.add_ai_message(answer_content)
    
    latency_ms = round((time.perf_counter() - t0) * 1000)
    yield {
        "type": "done",
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
        "session_id": session_id,
    }


# ── Memory Management ─────────────────────────────────────────────────────────
def get_memory_stats(session_id: Optional[str] = None) -> dict:
    """Get memory statistics."""
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
    """Clear memory for a session or all sessions."""
    store = get_memory_store()
    if session_id:
        store.clear_session(session_id)
        return {"message": f"Cleared session {session_id}"}
    else:
        # Clear all
        for sid in store.get_all_sessions():
            store.clear_session(sid)
        return {"message": "Cleared all sessions"}


# ── Utility ───────────────────────────────────────────────────────────────────
def get_stats() -> dict:
    """Get agent stats."""
    return {
        "num_tools": len(ALL_TOOLS),
        "tool_names": [t.name for t in ALL_TOOLS],
        "model": DEFAULT_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
    }
