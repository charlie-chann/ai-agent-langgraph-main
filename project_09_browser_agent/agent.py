# agent.py — Browser Automation Agent (LangGraph ReAct loop)
from __future__ import annotations

import time
from typing import TypedDict, Annotated, Sequence
import operator

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, BROWSER_MAX_STEPS
from prompts.browser_prompts import PLANNER_PROMPT, REPORT_PROMPT
from tools.browser_tool import BROWSER_TOOLS
from tools.task_parser import parse_task, sanitize_instruction


# ── State ─────────────────────────────────────────────────────────────────────
class BrowserState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    instruction: str
    step_count: int
    pages_visited: list[str]
    raw_content: str
    final_report: str
    total_latency_ms: float
    step_log: list[dict]


# ── LLM + Tools ──────────────────────────────────────────────────────────────
def _llm_with_tools() -> ChatOllama:
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )
    return llm.bind_tools(BROWSER_TOOLS)


def _llm_plain() -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )


# ── Nodes ─────────────────────────────────────────────────────────────────────
def node_plan_and_act(state: BrowserState) -> BrowserState:
    """Main ReAct node: thinks and decides which tool to call."""
    t0 = time.perf_counter()
    step = state.get("step_count", 0)
    logger.info(f"[BrowserAgent] Step {step + 1}/{BROWSER_MAX_STEPS}")

    llm = _llm_with_tools()
    # Build prompt messages
    system_msg = PLANNER_PROMPT.messages[0].format(max_steps=BROWSER_MAX_STEPS)
    history = list(state.get("messages", []))
    if not history:
        history = [HumanMessage(content=state["instruction"])]

    response = llm.invoke([system_msg] + history)

    elapsed = round((time.perf_counter() - t0) * 1000)
    log = state.get("step_log", [])
    log.append({
        "step": step + 1,
        "preview": (response.content or "[tool_call]")[:200],
        "time_ms": elapsed,
    })

    return {
        "messages": [response],
        "step_count": step + 1,
        "step_log": log,
    }


def node_tools(state: BrowserState) -> BrowserState:
    """Execute tool calls and collect raw content."""
    tool_node = ToolNode(BROWSER_TOOLS)
    result = tool_node.invoke(state)

    # Track pages visited and accumulate raw content
    pages = state.get("pages_visited", [])
    raw = state.get("raw_content", "")
    for msg in result.get("messages", []):
        if isinstance(msg, ToolMessage):
            raw += f"\n\n---\n[工具结果: {msg.name}]\n{msg.content[:2000]}"
            # Try to find URLs in tool messages
            import re
            urls = re.findall(r'https?://[^\s]+', msg.content)
            pages.extend(urls)

    return {
        **result,
        "pages_visited": pages,
        "raw_content": raw,
    }


def node_synthesize_report(state: BrowserState) -> BrowserState:
    """Synthesize all collected content into a final report."""
    t0 = time.perf_counter()
    logger.info("[BrowserAgent] Synthesizing final report...")

    task = parse_task(state["instruction"])
    chain = REPORT_PROMPT | _llm_plain()

    full_report = ""
    for chunk in chain.stream({
        "task_type": task.task_type,
        "instruction": state["instruction"],
        "raw_content": state.get("raw_content", "（无收集内容）")[-6000:],
    }):
        full_report += chunk.content

    elapsed = round((time.perf_counter() - t0) * 1000)
    log = state.get("step_log", [])
    log.append({"step": "synthesize", "preview": full_report[:200], "time_ms": elapsed})

    return {
        "final_report": full_report,
        "step_log": log,
        "total_latency_ms": sum(s.get("time_ms", 0) for s in log),
    }


# ── Routing ───────────────────────────────────────────────────────────────────
def _should_continue(state: BrowserState) -> str:
    """Route: continue tool loop or move to synthesis."""
    messages = state.get("messages", [])
    if not messages:
        return "synthesize"

    last = messages[-1]
    step = state.get("step_count", 0)

    # If max steps reached, synthesize
    if step >= BROWSER_MAX_STEPS:
        logger.info(f"[BrowserAgent] Max steps ({BROWSER_MAX_STEPS}) reached, synthesizing")
        return "synthesize"

    # If last message has tool calls, execute them
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"

    # LLM produced final text (no more tool calls)
    return "synthesize"


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(BrowserState)

    graph.add_node("plan_and_act", node_plan_and_act)
    graph.add_node("tools", node_tools)
    graph.add_node("synthesize", node_synthesize_report)

    graph.set_entry_point("plan_and_act")
    graph.add_conditional_edges("plan_and_act", _should_continue, {
        "tools": "tools",
        "synthesize": "synthesize",
    })
    graph.add_edge("tools", "plan_and_act")
    graph.add_edge("synthesize", END)

    return graph.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


# ── Public API ────────────────────────────────────────────────────────────────
def run_browser_task(instruction: str) -> dict:
    """Run a browser automation task and return the final state."""
    instruction = sanitize_instruction(instruction)
    logger.info(f"[BrowserAgent] Task: {instruction!r}")

    initial_state: BrowserState = {
        "messages": [HumanMessage(content=instruction)],
        "instruction": instruction,
        "step_count": 0,
        "pages_visited": [],
        "raw_content": "",
        "final_report": "",
        "total_latency_ms": 0.0,
        "step_log": [],
    }

    graph = get_graph()
    final = graph.invoke(initial_state)
    return final


def stream_browser_task(instruction: str):
    """Stream browser task execution events."""
    instruction = sanitize_instruction(instruction)

    initial_state: BrowserState = {
        "messages": [HumanMessage(content=instruction)],
        "instruction": instruction,
        "step_count": 0,
        "pages_visited": [],
        "raw_content": "",
        "final_report": "",
        "total_latency_ms": 0.0,
        "step_log": [],
    }

    graph = get_graph()
    for event in graph.stream(initial_state, stream_mode="updates"):
        yield event
