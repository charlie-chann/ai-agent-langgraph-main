# agent.py — Multi-Agent Collaboration System (LangGraph) v2.0
from __future__ import annotations

import json
import time
from typing import TypedDict, Annotated, Optional, Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from loguru import logger

from config import (
    settings,
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, CREATIVE_TEMPERATURE,
    MAX_REVISION_LOOPS, CRITIC_PASS_SCORE,
    SCENARIO_MARKET_RESEARCH, SCENARIO_SOCIAL_MEDIA,
)
from prompts.agent_prompts import (
    PLANNER_PROMPT, RESEARCHER_PROMPT,
    WRITER_MARKET_PROMPT, WRITER_SOCIAL_PROMPT,
    CRITIC_PROMPT, SUMMARIZER_PROMPT,
)
from tools.search_tool import multi_search


# ── Shared State ───────────────────────────────────────────────────────────────
class MultiAgentState(TypedDict):
    task: str
    scenario: str
    plan: dict
    search_results: str
    research: str
    content: str
    critique: dict
    summary: str
    revision_count: int
    agent_log: list[dict]
    final_output: str
    total_latency_ms: float


def _llm(creative: bool = False) -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=CREATIVE_TEMPERATURE if creative else TEMPERATURE,
    )


def _log_step(state: MultiAgentState, agent: str, output: str, t0: float) -> None:
    state["agent_log"].append({
        "agent": agent,
        "output_preview": output[:300],
        "time_ms": round((time.perf_counter() - t0) * 1000),
    })


# ── Agent Nodes ────────────────────────────────────────────────────────────────
def node_planner(state: MultiAgentState) -> MultiAgentState:
    t0 = time.perf_counter()
    logger.info("[Planner] Planning task...")
    chain = PLANNER_PROMPT | _llm()
    result = chain.invoke({"task": state["task"], "scenario": state["scenario"]})

    try:
        plan = json.loads(result.content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', result.content, re.DOTALL)
        plan = json.loads(match.group()) if match else {
            "goal": state["task"],
            "research_questions": [state["task"]],
            "content_sections": ["Overview", "Analysis", "Conclusion"],
            "tone": "professional",
            "target_audience": "general",
        }

    state["plan"] = plan
    _log_step(state, "Planner", json.dumps(plan)[:300], t0)
    return state


def node_researcher(state: MultiAgentState) -> MultiAgentState:
    t0 = time.perf_counter()
    logger.info("[Researcher] Searching...")
    questions = state["plan"].get("research_questions", [state["task"]])
    raw_results = multi_search(questions)
    state["search_results"] = raw_results

    chain = RESEARCHER_PROMPT | _llm()
    result = chain.invoke({
        "research_questions": "\n".join(f"- {q}" for q in questions),
        "search_results": raw_results,
    })
    state["research"] = result.content
    _log_step(state, "Researcher", result.content, t0)
    return state


def node_writer(state: MultiAgentState) -> MultiAgentState:
    t0 = time.perf_counter()
    logger.info("[Writer] Writing content...")
    plan = state["plan"]

    if state["scenario"] == SCENARIO_SOCIAL_MEDIA:
        chain = WRITER_SOCIAL_PROMPT | _llm(creative=True)
    else:
        chain = WRITER_MARKET_PROMPT | _llm(creative=True)

    result = chain.invoke({
        "plan": json.dumps(plan, ensure_ascii=False),
        "research": state["research"],
        "tone": plan.get("tone", "professional"),
        "target_audience": plan.get("target_audience", "general audience"),
    })
    state["content"] = result.content
    _log_step(state, "Writer", result.content, t0)
    return state


def node_critic(state: MultiAgentState) -> MultiAgentState:
    t0 = time.perf_counter()
    logger.info("[Critic] Evaluating content...")
    chain = CRITIC_PROMPT | _llm()
    result = chain.invoke({
        "goal": state["plan"].get("goal", state["task"]),
        "content": state["content"],
    })

    try:
        critique = json.loads(result.content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', result.content, re.DOTALL)
        critique = json.loads(match.group()) if match else {
            "overall_score": 8, "verdict": "pass",
            "strengths": [], "improvements": [],
        }

    state["critique"] = critique
    state["revision_count"] = state.get("revision_count", 0) + 1
    _log_step(state, "Critic", json.dumps(critique)[:300], t0)
    return state


def node_summarizer(state: MultiAgentState) -> MultiAgentState:
    t0 = time.perf_counter()
    logger.info("[Summarizer] Creating summary...")
    chain = SUMMARIZER_PROMPT | _llm()
    result = chain.invoke({"content": state["content"]})
    state["summary"] = result.content
    state["final_output"] = f"{state['content']}\n\n---\n\n## Executive Summary\n{result.content}"
    _log_step(state, "Summarizer", result.content, t0)
    return state


# ── Routing ────────────────────────────────────────────────────────────────────
def _route_after_critic(state: MultiAgentState) -> str:
    score = state["critique"].get("overall_score", 10)
    verdict = state["critique"].get("verdict", "pass")
    if verdict == "pass" or score >= CRITIC_PASS_SCORE or state["revision_count"] >= MAX_REVISION_LOOPS:
        logger.info(f"[Critic] Score={score} → Summarizer")
        return "summarizer"
    logger.info(f"[Critic] Score={score} → revise (loop {state['revision_count']})")
    return "writer"


# ── Build Graph ────────────────────────────────────────────────────────────────
def build_graph():
    g = StateGraph(MultiAgentState)
    g.add_node("planner", node_planner)
    g.add_node("researcher", node_researcher)
    g.add_node("writer", node_writer)
    g.add_node("critic", node_critic)
    g.add_node("summarizer", node_summarizer)

    g.set_entry_point("planner")
    g.add_edge("planner", "researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer", "critic")
    g.add_conditional_edges("critic", _route_after_critic, {
        "writer": "writer",
        "summarizer": "summarizer",
    })
    g.add_edge("summarizer", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── Public API ─────────────────────────────────────────────────────────────────
def run(task: str, scenario: str = SCENARIO_MARKET_RESEARCH) -> dict:
    """Run the full multi-agent pipeline."""
    t0 = time.perf_counter()
    initial: MultiAgentState = {
        "task": task,
        "scenario": scenario,
        "plan": {},
        "search_results": "",
        "research": "",
        "content": "",
        "critique": {},
        "summary": "",
        "revision_count": 0,
        "agent_log": [],
        "final_output": "",
        "total_latency_ms": 0,
    }
    result = get_graph().invoke(initial)
    result["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return result


def run_stream(task: str, scenario: str = SCENARIO_MARKET_RESEARCH) -> Generator[dict, None, None]:
    """Stream agent progress events."""
    t0 = time.perf_counter()
    initial: MultiAgentState = {
        "task": task,
        "scenario": scenario,
        "plan": {},
        "search_results": "",
        "research": "",
        "content": "",
        "critique": {},
        "summary": "",
        "revision_count": 0,
        "agent_log": [],
        "final_output": "",
        "total_latency_ms": 0,
    }

    for event in get_graph().stream(initial, stream_mode="updates"):
        for node_name, node_state in event.items():
            log = node_state.get("agent_log", [])
            last = log[-1] if log else {}
            yield {
                "type": "node_complete",
                "agent": node_name,
                "preview": last.get("output_preview", ""),
                "time_ms": last.get("time_ms", 0),
            }

    total_ms = round((time.perf_counter() - t0) * 1000)
    yield {"type": "done", "total_latency_ms": total_ms}
