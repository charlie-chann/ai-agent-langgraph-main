# agent.py — HR Recruitment Screening Agent (LangGraph)
from __future__ import annotations

import json
import time
from typing import TypedDict, Annotated, Sequence
import operator

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from loguru import logger

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    SCORE_THRESHOLD_SHORTLIST, SCORE_THRESHOLD_REJECT,
)
from prompts.hr_prompts import HR_AGENT_PROMPT, RESUME_ANALYSIS_PROMPT, INTERVIEW_QUESTIONS_PROMPT
from tools.resume_scorer import score_resume, batch_score, JobRequirement, ScoringResult
from tools.candidate_db import (
    add_candidate, get_candidate, update_candidate_status,
    list_candidates, set_candidate_score, get_all_candidates,
)
from tools.report_tool import generate_screening_report, list_reports

HR_TOOLS = [
    add_candidate,
    get_candidate,
    update_candidate_status,
    list_candidates,
    set_candidate_score,
    generate_screening_report,
    list_reports,
]


# ── State ─────────────────────────────────────────────────────────────────────
class HRState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    job_requirement: dict           # JobRequirement serialized
    screening_results: list[dict]   # ScoringResult.to_dict() list
    final_report: str
    total_latency_ms: float
    step_log: list[dict]


# ── LLM ───────────────────────────────────────────────────────────────────────
def _llm_with_tools() -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE,
    ).bind_tools(HR_TOOLS)


def _llm_plain() -> ChatOllama:
    return ChatOllama(
        model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE,
    )


# ── Nodes ─────────────────────────────────────────────────────────────────────
def node_hr_agent(state: HRState) -> HRState:
    """Main HR agent reasoning node."""
    t0 = time.perf_counter()
    system_msg = HR_AGENT_PROMPT.messages[0]
    history = list(state.get("messages", []))

    llm = _llm_with_tools()
    response = llm.invoke([system_msg] + history)

    elapsed = round((time.perf_counter() - t0) * 1000)
    log = state.get("step_log", [])
    log.append({"step": "hr_agent", "preview": (response.content or "[tool_call]")[:200], "time_ms": elapsed})

    return {"messages": [response], "step_log": log}


def node_tools(state: HRState) -> HRState:
    """Execute HR tool calls."""
    tool_node = ToolNode(HR_TOOLS)
    return tool_node.invoke(state)


def _should_continue(state: HRState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return END
    last = messages[-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


# ── Graph ─────────────────────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(HRState)
    graph.add_node("hr_agent", node_hr_agent)
    graph.add_node("tools", node_tools)
    graph.set_entry_point("hr_agent")
    graph.add_conditional_edges("hr_agent", _should_continue, {
        "tools": "tools",
        END: END,
    })
    graph.add_edge("tools", "hr_agent")
    return graph.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


# ── High-Level Screening API ─────────────────────────────────────────────────
def screen_candidates(resumes: list[dict], job_req: JobRequirement) -> list[ScoringResult]:
    """Screen a batch of resumes against a job requirement (no LLM needed)."""
    return batch_score(resumes, job_req)


def generate_interview_questions(
    position: str,
    required_skills: list[str],
    candidate_skills: list[str],
    years_exp: int,
) -> str:
    """Generate tailored interview questions for a shortlisted candidate."""
    chain = INTERVIEW_QUESTIONS_PROMPT | _llm_plain()
    full_text = ""
    for chunk in chain.stream({
        "position": position,
        "required_skills": ", ".join(required_skills),
        "candidate_skills": ", ".join(candidate_skills),
        "years_exp": years_exp,
    }):
        full_text += chunk.content
    return full_text


def parse_resume_with_llm(resume_text: str) -> dict:
    """Use LLM to parse unstructured resume text into structured dict."""
    chain = RESUME_ANALYSIS_PROMPT | _llm_plain()
    result = chain.invoke({"resume_text": resume_text[:5000]})
    try:
        import re
        # Extract JSON from response
        text = result.content
        match = re.search(r'\{.*\}', text, re.DOTALL)
        return json.loads(match.group()) if match else {}
    except Exception:
        return {}


def run_hr_chat(message: str, history: list[dict] | None = None) -> str:
    """Run a conversational HR assistant turn."""
    messages = []
    for h in (history or []):
        if h.get("role") == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h.get("role") == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))

    state: HRState = {
        "messages": messages,
        "job_requirement": {},
        "screening_results": [],
        "final_report": "",
        "total_latency_ms": 0.0,
        "step_log": [],
    }
    graph = get_graph()
    result = graph.invoke(state)
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)


def stream_hr_chat(message: str, history: list[dict] | None = None):
    """Stream HR assistant response."""
    messages = []
    for h in (history or []):
        if h.get("role") == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h.get("role") == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=message))

    state: HRState = {
        "messages": messages,
        "job_requirement": {},
        "screening_results": [],
        "final_report": "",
        "total_latency_ms": 0.0,
        "step_log": [],
    }
    graph = get_graph()
    for event in graph.stream(state, stream_mode="updates"):
        yield event
