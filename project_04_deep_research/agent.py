# agent.py — Deep Research Agent (LangGraph iterative search loop)
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


# ── State ──────────────────────────────────────────────────────────────────────
class ResearchState(TypedDict):
    topic: str
    all_queries: list[str]          # all queries issued so far
    search_results_history: list    # [{round, queries, raw_results}]
    research_notes: str             # synthesized notes (updated each round)
    gap_analysis: dict              # latest gap analyzer output
    report_draft: str
    final_report: str
    round: int
    coverage_score: float
    saved_path: str
    total_latency_ms: float
    step_log: list[dict]            # [{step, preview, time_ms}]


def _llm(creative: bool = False) -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=CREATIVE_TEMPERATURE if creative else TEMPERATURE,
    )


def _parse_json(text: str, fallback: dict) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return fallback


def _parse_json_list(text: str) -> list[str]:
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except Exception:
        pass
    # Try to extract from markdown code block
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    # Fallback: parse line by line
    lines = [ln.strip().strip('"-,') for ln in text.splitlines() if ln.strip()]
    return [ln for ln in lines if len(ln) > 5][:SEARCHES_PER_ROUND]


def _log(state: ResearchState, step: str, preview: str, t0: float) -> None:
    state["step_log"].append({
        "step": step,
        "preview": preview[:300],
        "time_ms": round((time.perf_counter() - t0) * 1000),
    })


# ── Nodes ──────────────────────────────────────────────────────────────────────
def node_generate_queries(state: ResearchState) -> ResearchState:
    t0 = time.perf_counter()
    round_num = state.get("round", 0)
    logger.info(f"[QueryGen] Round {round_num + 1}")

    already = ", ".join(state.get("all_queries", [])[-10:]) or "none"
    chain = QUERY_GEN_PROMPT | _llm()
    result = chain.invoke({
        "topic": state["topic"],
        "n": SEARCHES_PER_ROUND,
        "already_searched": already,
    })
    queries = _parse_json_list(result.content)
    if not queries:
        queries = [f"{state['topic']} overview", f"{state['topic']} statistics 2025"]

    state["all_queries"] = state.get("all_queries", []) + queries
    _log(state, f"QueryGen R{round_num + 1}", str(queries), t0)
    # Store current round queries for searcher
    state["_current_queries"] = queries
    return state


def node_search(state: ResearchState) -> ResearchState:
    t0 = time.perf_counter()
    queries = state.get("_current_queries", [state["topic"]])
    logger.info(f"[Search] Searching {len(queries)} queries...")

    raw = batch_search(queries)
    formatted = format_search_results(raw)

    history = state.get("search_results_history", [])
    history.append({
        "round": state.get("round", 0),
        "queries": queries,
        "results_preview": formatted[:500],
    })
    state["search_results_history"] = history
    state["_latest_search_results"] = formatted
    _log(state, f"Search R{state.get('round', 0) + 1}", formatted, t0)
    return state


def node_synthesize(state: ResearchState) -> ResearchState:
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
    t0 = time.perf_counter()
    logger.info(f"[GapAnalysis] Round {state['round']}/{MAX_SEARCH_ROUNDS}")

    chain = GAP_ANALYZER_PROMPT | _llm()
    result = chain.invoke({
        "topic": state["topic"],
        "research_summary": state.get("research_notes", "")[:3000],
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
    # Inject follow-up queries for next round
    state["_current_queries"] = gap.get("followup_queries", [])[: SEARCHES_PER_ROUND]
    _log(state, f"GapAnalysis R{state['round']}", json.dumps(gap)[:300], t0)
    return state


def _should_continue_research(state: ResearchState) -> str:
    score = state.get("coverage_score", 0)
    round_num = state.get("round", 0)
    gap = state.get("gap_analysis", {})
    ready = gap.get("ready_to_write", False)

    if ready or score >= SUFFICIENCY_THRESHOLD or round_num >= MAX_SEARCH_ROUNDS:
        logger.info(f"[Router] score={score:.2f} round={round_num} → write_report")
        return "write_report"
    logger.info(f"[Router] score={score:.2f} round={round_num} → more_research")
    return "generate_queries"


def node_write_report(state: ResearchState) -> ResearchState:
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
    t0 = time.perf_counter()
    logger.info("[Polisher] Polishing report...")

    chain = POLISHER_PROMPT | _llm(creative=True)
    result = chain.invoke({"report": state.get("report_draft", "")})
    state["final_report"] = result.content
    _log(state, "Polisher", result.content, t0)

    # Auto-save
    try:
        path = save_report(state["topic"], state["final_report"])
        state["saved_path"] = str(path)
    except Exception as e:
        logger.warning(f"Could not save report: {e}")
        state["saved_path"] = ""

    return state


# ── Build Graph ────────────────────────────────────────────────────────────────
def build_graph():
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
    g.add_conditional_edges("gap_analysis", _should_continue_research, {
        "generate_queries": "generate_queries",
        "write_report": "write_report",
    })
    g.add_edge("write_report", "polish_report")
    g.add_edge("polish_report", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public API ─────────────────────────────────────────────────────────────────
def research(topic: str) -> dict:
    """Run full deep research pipeline. Returns final report + metadata."""
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
    """Stream research progress events."""
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
