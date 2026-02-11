"""
agent.py — Deep Research Agent 核心（LangGraph 迭代搜索循环）

【职责】
基于 LangGraph 构建多轮「查询生成 → 搜索 → 综合 → 缺口分析」研究循环，
在覆盖度达标或达到轮次上限后撰写并润色报告，提供同步与流式两种调用入口。

【设计原因】
LangGraph 状态图清晰表达条件分支（继续研究 vs 写报告），
各节点职责单一便于调试；TypedDict 状态便于类型检查与流式事件推送。
"""
from __future__ import annotations

import json
import re
import time
from typing import TypedDict, Generator

from langchain_community.chat_models import ChatOllama
from langgraph.graph import StateGraph, END
from loguru import logger

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, CREATIVE_TEMPERATURE,
    MAX_SEARCH_ROUNDS, SEARCHES_PER_ROUND, SUFFICIENCY_THRESHOLD,
)
from prompts.research_prompts import (
    QUERY_GEN_PROMPT, GAP_ANALYZER_PROMPT,
    SYNTHESIZER_PROMPT, REPORT_WRITER_PROMPT, POLISHER_PROMPT,
)
from tools.search_tool import batch_search, format_search_results
from tools.report_saver import save_report


# ── 状态定义 ──────────────────────────────────────────────────────────────────
class ResearchState(TypedDict):
    """
    LangGraph 图节点间共享的研究状态。

    各字段在流水线不同阶段被读写，最终 invoke/stream 返回完整状态供 API/UI 使用。
    """
    topic: str
    all_queries: list[str]          # 迄今发出的全部搜索查询
    search_results_history: list    # [{round, queries, raw_results}]
    research_notes: str             # 综合后的研究笔记（每轮更新）
    gap_analysis: dict              # 最新一轮缺口分析 JSON
    report_draft: str
    final_report: str
    round: int
    coverage_score: float
    saved_path: str
    total_latency_ms: float
    step_log: list[dict]            # [{step, preview, time_ms}] 步骤审计日志


def _llm(creative: bool = False) -> ChatOllama:
    """
    创建 ChatOllama 实例。

    Args:
        creative: True 时使用较高 temperature，用于报告撰写与润色

    Returns:
        配置好的 ChatOllama 模型
    """
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=CREATIVE_TEMPERATURE if creative else TEMPERATURE,
    )


def _parse_json(text: str, fallback: dict) -> dict:
    """
    从 LLM 输出中解析 JSON 对象，容错处理非标准格式。

    Args:
        text: LLM 原始输出文本
        fallback: 解析失败时返回的默认字典

    Returns:
        解析得到的 dict 或 fallback
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试从文本中提取第一个 {...} 块（模型常在 JSON 外加说明文字）
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return fallback


def _parse_json_list(text: str) -> list[str]:
    """
    从 LLM 输出中解析 JSON 字符串数组（搜索查询列表）。

    Args:
        text: LLM 原始输出

    Returns:
        查询字符串列表；解析失败时按行启发式提取
    """
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except Exception:
        pass
    # 尝试从 markdown 代码块或正文中提取 [...] 数组
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    # 兜底：按行拆分，过滤过短行，限制条数
    lines = [ln.strip().strip('"-,') for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if len(ln) > 5][:SEARCHES_PER_ROUND]


def _log(state: ResearchState, step: str, preview: str, t0: float) -> None:
    """
    向 step_log 追加一步骤记录，供 UI 时间线与调试使用。

    Args:
        state: 当前图状态（就地修改 step_log）
        step: 步骤名称
        preview: 输出预览（截断至 300 字符）
        t0: perf_counter 起始时间
    """
    state["step_log"].append({
        "step": step,
        "preview": preview[:300],
        "time_ms": round((time.perf_counter() - t0) * 1000),
    })


# ── 图节点 ──────────────────────────────────────────────────────────────────────
def node_generate_queries(state: ResearchState) -> ResearchState:
    """
    查询生成节点：根据主题与已搜查询，生成本轮待执行的搜索词。

    输出写入 _current_queries 供 search 节点使用，并累加到 all_queries。
    """
    t0 = time.perf_counter()
    round_num = state.get("round", 0)
    logger.info(f"[QueryGen] Round {round_num + 1}")

    # 仅展示最近 10 条已搜查询，避免 prompt 过长
    already = ", ".join(state.get("all_queries", [])[-10:]) or "none"
    chain = QUERY_GEN_PROMPT | _llm()
    result = chain.invoke({
        "topic": state["topic"],
        "n": SEARCHES_PER_ROUND,
        "already_searched": already,
    })
    queries = _parse_json_list(result.content)
    # 解析失败时的默认查询，保证流水线可继续
    if not queries:
        queries = [f"{state['topic']} overview", f"{state['topic']} statistics 2025"]

    state["all_queries"] = state.get("all_queries", []) + queries
    _log(state, f"QueryGen R{round_num + 1}", str(queries), t0)
    # 暂存本轮查询，供 searcher 节点读取（非 TypedDict 正式字段，运行时扩展）
    state["_current_queries"] = queries
    return state


def node_search(state: ResearchState) -> ResearchState:
    """
    搜索节点：对 _current_queries 批量调用 web 搜索，格式化结果并写入历史。
    """
    t0 = time.perf_counter()
    queries = state.get("_current_queries", [state["topic"]])
    logger.info(f"[Search] Searching {len(queries)} queries...")

    raw = batch_search(queries)
    formatted = format_search_results(raw)

    history = state.get("search_results_history", [])
    history.append({
        "round": state.get("round", 0),
        "queries": queries,
        "results_preview": formatted[:500],  # 历史中仅保留预览，控制状态体积
    })
    state["search_results_history"] = history
    state["_latest_search_results"] = formatted
    _log(state, f"Search R{state.get('round', 0) + 1}", formatted, t0)
    return state


def node_synthesize(state: ResearchState) -> ResearchState:
    """
    综合节点：将本轮搜索结果与既有笔记合并，更新 research_notes 并递增 round。
    """
    t0 = time.perf_counter()
    logger.info("[Synthesizer] Synthesizing research notes...")

    chain = SYNTHESIZER_PROMPT | _llm()
    result = chain.invoke({
        "topic": state["topic"],
        "round": state.get("round", 0) + 1,
        "new_results": state.get("_latest_search_results", ""),
        "previous_notes": state.get("research_notes", "(none yet)"),
    })
    state["research_notes"] = result.content
    state["round"] = state.get("round", 0) + 1
    _log(state, f"Synthesizer R{state['round']}", result.content, t0)
    return state


def node_gap_analysis(state: ResearchState) -> ResearchState:
    """
    缺口分析节点：评估覆盖度，决定是否继续研究；若继续则注入 followup_queries。
    """
    t0 = time.perf_counter()
    logger.info(f"[GapAnalysis] Round {state['round']}/{MAX_SEARCH_ROUNDS}")

    chain = GAP_ANALYZER_PROMPT | _llm()
    result = chain.invoke({
        "topic": state["topic"],
        "research_summary": state.get("research_notes", "")[:3000],  # 截断控制 token
        "round": state["round"],
        "max_rounds": MAX_SEARCH_ROUNDS,
    })
    gap = _parse_json(result.content, {
        "coverage_score": 0.7,
        "gaps": [],
        "followup_queries": [],
        "ready_to_write": state["round"] >= MAX_SEARCH_ROUNDS,
    })
    state["gap_analysis"] = gap
    state["coverage_score"] = float(gap.get("coverage_score", 0.7))
    # 下一轮 generate_queries 可跳过重新生成，直接使用缺口分析给出的查询
    state["_current_queries"] = gap.get("followup_queries", [])[: SEARCHES_PER_ROUND]
    _log(state, f"GapAnalysis R{state['round']}", json.dumps(gap)[:300], t0)
    return state


def _should_continue_research(state: ResearchState) -> str:
    """
    条件路由：根据覆盖度、ready_to_write 标志与轮次决定继续研究或进入写报告。

    Returns:
        "write_report" 或 "generate_queries"（LangGraph 条件边键名）
    """
    score = state.get("coverage_score", 0)
    round_num = state.get("round", 0)
    gap = state.get("gap_analysis", {})
    ready = gap.get("ready_to_write", False)

    # 任一终止条件满足即进入报告阶段
    if ready or score >= SUFFICIENCY_THRESHOLD or round_num >= MAX_SEARCH_ROUNDS:
        logger.info(f"[Router] score={score:.2f} round={round_num} → write_report")
        return "write_report"
    logger.info(f"[Router] score={score:.2f} round={round_num} → more_research")
    return "generate_queries"


def node_write_report(state: ResearchState) -> ResearchState:
    """
    报告撰写节点：基于 research_notes 生成 report_draft（使用 creative 温度）。
    """
    t0 = time.perf_counter()
    logger.info("[Writer] Writing report...")

    chain = REPORT_WRITER_PROMPT | _llm(creative=True)
    result = chain.invoke({
        "topic": state["topic"],
        "research_notes": state.get("research_notes", ""),
    })
    state["report_draft"] = result.content
    _log(state, "Writer", result.content, t0)
    return state


def node_polish_report(state: ResearchState) -> ResearchState:
    """
    报告润色节点：优化初稿并写入 final_report，随后自动持久化到磁盘。
    """
    t0 = time.perf_counter()
    logger.info("[Polisher] Polishing report...")

    chain = POLISHER_PROMPT | _llm(creative=True)
    result = chain.invoke({"report": state.get("report_draft", "")})
    state["final_report"] = result.content
    _log(state, "Polisher", result.content, t0)

    # 润色完成后自动保存，失败不阻断图执行
    try:
        path = save_report(state["topic"], state["final_report"])
        state["saved_path"] = str(path)
    except Exception as e:
        logger.warning(f"Could not save report: {e}")
        state["saved_path"] = ""

    return state


# ── 构建 LangGraph 图 ───────────────────────────────────────────────────────────
def build_graph():
    """
    组装 StateGraph：定义节点、边与条件分支，编译为可 invoke 的 Runnable。

    Returns:
        编译后的 LangGraph 应用
    """
    g = StateGraph(ResearchState)
    g.add_node("generate_queries", node_generate_queries)
    g.add_node("search", node_search)
    g.add_node("synthesize", node_synthesize)
    g.add_node("gap_analysis", node_gap_analysis)
    g.add_node("write_report", node_write_report)
    g.add_node("polish_report", node_polish_report)

    g.set_entry_point("generate_queries")
    g.add_edge("generate_queries", "search")
    g.add_edge("search", "synthesize")
    g.add_edge("synthesize", "gap_analysis")
    # 缺口分析后根据覆盖度决定循环或写报告
    g.add_conditional_edges("gap_analysis", _should_continue_research, {
        "generate_queries": "generate_queries",
        "write_report": "write_report",
    })
    g.add_edge("write_report", "polish_report")
    g.add_edge("polish_report", END)

    return g.compile()


_graph = None


def get_graph():
    """
    懒加载单例图实例，避免重复编译开销。

    Returns:
        全局缓存的编译图
    """
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── 对外 API ────────────────────────────────────────────────────────────────────
def research(topic: str) -> dict:
    """
    运行完整深度研究流水线（同步阻塞）。

    Args:
        topic: 研究主题

    Returns:
        最终 ResearchState 字典，含 final_report、metadata 与 total_latency_ms
    """
    t0 = time.perf_counter()
    initial: ResearchState = {
        "topic": topic,
        "all_queries": [],
        "search_results_history": [],
        "research_notes": "",
        "gap_analysis": {},
        "report_draft": "",
        "final_report": "",
        "round": 0,
        "coverage_score": 0.0,
        "saved_path": "",
        "total_latency_ms": 0,
        "step_log": [],
    }
    result = get_graph().invoke(initial)
    result["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return result


def research_stream(topic: str) -> Generator[dict, None, None]:
    """
    流式推送研究进度事件，供 SSE / Streamlit 实时 UI 使用。

    Args:
        topic: 研究主题

    Yields:
        type=step 的节点完成事件，最后 yield type=done 含总耗时
    """
    t0 = time.perf_counter()
    initial: ResearchState = {
        "topic": topic,
        "all_queries": [],
        "search_results_history": [],
        "research_notes": "",
        "gap_analysis": {},
        "report_draft": "",
        "final_report": "",
        "round": 0,
        "coverage_score": 0.0,
        "saved_path": "",
        "total_latency_ms": 0,
        "step_log": [],
    }

    for event in get_graph().stream(initial, stream_mode="updates"):
        for node_name, node_state in event.items():
            log = node_state.get("step_log", [])
            last = log[-1] if log else {}
            extra = {}
            # gap_analysis 节点额外推送覆盖度与轮次，便于 UI 展示进度
            if node_name == "gap_analysis":
                extra["coverage_score"] = node_state.get("coverage_score", 0)
                extra["round"] = node_state.get("round", 0)
            yield {
                "type": "step",
                "node": node_name,
                "preview": last.get("preview", "")[:200],
                "time_ms": last.get("time_ms", 0),
                **extra,
            }

    yield {
        "type": "done",
        "total_latency_ms": round((time.perf_counter() - t0) * 1000),
    }
