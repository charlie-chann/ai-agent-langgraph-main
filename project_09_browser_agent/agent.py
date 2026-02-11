# agent.py — Browser Automation Agent (LangGraph ReAct loop)
#
# 【架构】LangGraph 三节点 ReAct 循环：
#   plan_and_act（LLM 思考）→ tools（执行浏览器工具）→ 回到 plan_and_act
#   达到停止条件后 → synthesize（生成报告）→ END
#
# 【执行入口】
#   graph.invoke()  → run_browser_task()  → API POST /task（同步）
#   graph.stream()  → stream_browser_task() → Streamlit UI / API POST /task/stream
from __future__ import annotations

import time
from typing import TypedDict, Annotated, Sequence
import operator

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, BROWSER_MAX_STEPS
from prompts.browser_prompts import PLANNER_PROMPT, REPORT_PROMPT
from tools.browser_tool import BROWSER_TOOLS
from tools.task_parser import parse_task, sanitize_instruction


# ── State：LangGraph 各节点共享的状态字典 ─────────────────────────────────────
class BrowserState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]  # 对话历史，add 表示自动追加
    instruction: str          # 用户原始任务指令
    step_count: int           # ReAct 已执行步数，用于 max_steps 保护
    pages_visited: list[str]  # 已访问 URL 列表（从工具结果提取）
    raw_content: str          # 工具返回内容的累积拼接，供最终报告使用
    final_report: str         # synthesize 节点产出的 Markdown 报告
    total_latency_ms: float   # 端到端耗时
    step_log: list[dict]      # 每步预览与耗时，供 UI 展示


# ── LLM + Tools ──────────────────────────────────────────────────────────────
def _llm_with_tools() -> ChatOllama:
    """带工具绑定的 LLM，供 plan_and_act 节点输出 tool_calls。"""
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )
    return llm.bind_tools(BROWSER_TOOLS)  # bind_tools 让 LLM 知道可调哪些工具


def _llm_plain() -> ChatOllama:
    """纯文本 LLM，供 synthesize 节点生成报告（不再调工具）。"""
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )


# ── Nodes：图节点函数（仅在被 graph.invoke/stream 调度时才真正执行）────
def node_plan_and_act(state: BrowserState) -> BrowserState:
    """ReAct 思考节点：llm.invoke 决定下一步调哪个浏览器工具。"""
    t0 = time.perf_counter()
    step = state.get("step_count", 0)
    logger.info(f"[BrowserAgent] Step {step + 1}/{BROWSER_MAX_STEPS}")

    llm = _llm_with_tools()
    # Build prompt messages
    system_msg = PLANNER_PROMPT.messages[0].format(max_steps=BROWSER_MAX_STEPS)
    history = list(state.get("messages", []))
    if not history:
        history = [HumanMessage(content=state["instruction"])]

    response = llm.invoke([system_msg] + history)  # 节点内 LLM 调用，非 graph.invoke

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
    """工具执行节点：读取上一步 AI 的 tool_calls，真正抓网页/搜页面。"""
    tool_node = ToolNode(BROWSER_TOOLS)  # 预构建工具执行器
    result = tool_node.invoke(state)     # 执行工具，返回 ToolMessage

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
    """报告合成节点：把 raw_content 交给 LLM 流式生成最终 Markdown 报告。"""
    t0 = time.perf_counter()
    logger.info("[BrowserAgent] Synthesizing final report...")

    task = parse_task(state["instruction"])
    chain = REPORT_PROMPT | _llm_plain()

    full_report = ""
    for chunk in chain.stream({  # chain.stream：逐 token 流式生成（内部用）
        "task_type": task.task_type,
        "instruction": state["instruction"],
        "raw_content": state.get("raw_content", "（无收集内容）")[-6000:],
    }):
        full_report += chunk.content  # 拼成完整报告后再写入 state

    elapsed = round((time.perf_counter() - t0) * 1000)
    log = state.get("step_log", [])
    log.append({"step": "synthesize", "preview": full_report[:200], "time_ms": elapsed})

    return {
        "final_report": full_report,
        "step_log": log,
        "total_latency_ms": sum(s.get("time_ms", 0) for s in log),
    }


# ── Routing：条件边路由函数（返回值决定下一跳节点名）────────────────────────
def _should_continue(state: BrowserState) -> str:
    """plan_and_act 之后的条件路由：继续调工具 or 进入 synthesize。"""
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


# ── Graph：定义节点与边（compile 只编译，不执行；执行在 invoke/stream）────
def build_graph() -> StateGraph:
    graph = StateGraph(BrowserState)  # 创建空图，指定状态类型

    # 注册节点：名字 → 函数（此时函数不会被调用）
    graph.add_node("plan_and_act", node_plan_and_act)
    graph.add_node("tools", node_tools)
    graph.add_node("synthesize", node_synthesize_report)

    graph.set_entry_point("plan_and_act")  # 入口：每次 invoke 从这里开始
    # 节点判断：根据 LLM 输出决定走 tools 还是 synthesize
    graph.add_conditional_edges("plan_and_act", _should_continue, {
        "tools": "tools",
        "synthesize": "synthesize",
    })
    # 固定边：工具执行完后，无条件回到 plan_and_act 继续思考（ReAct 循环）
    graph.add_edge("tools", "plan_and_act")
    # 固定边：报告生成完毕后，流程结束
    graph.add_edge("synthesize", END)

    # 编译图，返回可 invoke/stream 的对象（此时尚未执行任何节点）
    return graph.compile()


_GRAPH = None


def get_graph():
    """懒加载单例：compile 只做一次，后续 invoke/stream 复用同一图。"""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


# ── Public API：对外暴露的同步/流式执行入口 ───────────────────────────────────
def run_browser_task(instruction: str) -> dict:
    """同步执行：graph.invoke 跑完整张图后一次性返回最终 state。"""
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
    final = graph.invoke(initial_state)  # ★ 整张图的唯一 invoke 入口
    return final


def stream_browser_task(instruction: str):
    """流式执行：每完成一个节点 yield 一次，供 UI 实时更新进度。"""
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
    for event in graph.stream(initial_state, stream_mode="updates"):  # ★ UI 走这里
        yield event  # 每次 yield 形如 {"plan_and_act": {...}} 或 {"tools": {...}}
