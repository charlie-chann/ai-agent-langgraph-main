"""
agent.py — 真·多智能体协作系统 (LangGraph Supervisor + ReAct Sub-Agents) v3.0

【职责】
1. Supervisor LLM 动态派活，决定下一步由哪个子 Agent 执行
2. 五个子 Agent 均为独立 ReAct Agent（Researcher 自带搜索工具，可自主决定搜什么）
3. 通过 messages 通道传递 Agent 间协作上下文，同时保留 plan/research/content 等字段供 UI 展示

【设计原因】
1. Supervisor + Worker 模式：接近业界 Multi-Agent 编排，而非固定流水线
2. 各角色 langchain.agents.create_agent：Researcher 可自主多次搜索，而非代码写死 multi_search
3. 规则兜底 _rule_based_next：小模型 Supervisor 输出异常时仍可完成流水线
4. agent_log 仅记录 Worker 节点：UI 进度条与 v2 保持一致
"""
from __future__ import annotations

import json
import re
import time
from typing import TypedDict, Annotated, Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain.agents import create_agent
from loguru import logger

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, CREATIVE_TEMPERATURE,
    MAX_REVISION_LOOPS, CRITIC_PASS_SCORE, MAX_SUPERVISOR_TURNS, MAX_REACT_ITERATIONS,
    SCENARIO_MARKET_RESEARCH, SCENARIO_SOCIAL_MEDIA,
)
from prompts.agent_prompts import (
    SUPERVISOR_PROMPT,
    PLANNER_REACT_SYSTEM, RESEARCHER_REACT_SYSTEM,
    WRITER_MARKET_REACT_SYSTEM, WRITER_SOCIAL_REACT_SYSTEM,
    CRITIC_REACT_SYSTEM, SUMMARIZER_REACT_SYSTEM,
)
from tools.search_tool import RESEARCHER_TOOLS

WORKER_AGENTS = ("planner", "researcher", "writer", "critic", "summarizer")
VALID_NEXT = set(WORKER_AGENTS) | {"FINISH"}


# ── 共享状态 ───────────────────────────────────────────────────────────────────
class MultiAgentState(TypedDict):
    """
    LangGraph 各节点读写的全局状态字典。

    字段说明:
        task / scenario: 用户输入与业务场景
        messages: Agent 间协作消息通道（add_messages 自动合并）
        next_agent: Supervisor 决定的下一步 Worker 或 FINISH
        last_agent: 上一个完成的 Worker，供 Supervisor 判断是否需要 Critic
        supervisor_turns: Supervisor 已执行次数，防止无限循环
        plan / research / content / critique / summary: 各 Worker 结构化产出（UI 展示）
        search_results: Researcher 最终检索摘要（从 messages 或工具输出提取）
        revision_count: Critic 已执行次数
        agent_log: Worker 步骤日志
        final_output: 完整交付物
        total_latency_ms: 端到端耗时
    """
    task: str
    scenario: str
    messages: Annotated[list[BaseMessage], add_messages]
    next_agent: str
    last_agent: str
    supervisor_turns: int
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


# ── LLM 与子 Agent 工厂 ─────────────────────────────────────────────────────────
def _llm(creative: bool = False) -> ChatOllama:
    """创建 Ollama Chat 模型实例。"""
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=CREATIVE_TEMPERATURE if creative else TEMPERATURE,
    )


_sub_agents: dict[str, object] = {}


def _get_sub_agent(name: str, scenario: str = SCENARIO_MARKET_RESEARCH):
    """懒加载各角色 ReAct 子 Agent 单例。"""
    key = f"{name}:{scenario}" if name == "writer" else name
    if key in _sub_agents:
        return _sub_agents[key]

    if name == "planner":
        agent = create_agent(_llm(), tools=[], system_prompt=PLANNER_REACT_SYSTEM)
    elif name == "researcher":
        agent = create_agent(
            _llm(), tools=RESEARCHER_TOOLS, system_prompt=RESEARCHER_REACT_SYSTEM,
        )
    elif name == "writer":
        sys_prompt = (
            WRITER_SOCIAL_REACT_SYSTEM if scenario == SCENARIO_SOCIAL_MEDIA
            else WRITER_MARKET_REACT_SYSTEM
        )
        agent = create_agent(_llm(creative=True), tools=[], system_prompt=sys_prompt)
    elif name == "critic":
        agent = create_agent(_llm(), tools=[], system_prompt=CRITIC_REACT_SYSTEM)
    elif name == "summarizer":
        agent = create_agent(_llm(), tools=[], system_prompt=SUMMARIZER_REACT_SYSTEM)
    else:
        raise ValueError(f"Unknown sub-agent: {name}")

    _sub_agents[key] = agent
    return agent


def reset_agents() -> None:
    """清空子 Agent 缓存（测试或切换模型后调用）。"""
    global _sub_agents, _graph
    _sub_agents = {}
    _graph = None


# ── 工具函数 ───────────────────────────────────────────────────────────────────
def _parse_json(text: str, fallback: dict | None = None) -> dict:
    """从 LLM 输出解析 JSON 对象，容错处理 markdown 包裹等情况。"""
    fallback = fallback or {}
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return fallback


def _last_ai_content(messages: list[BaseMessage]) -> str:
    """取 messages 中最后一条 AI 回复的文本内容。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return ""


def _format_recent_messages(messages: list[BaseMessage], limit: int = 8) -> str:
    """格式化最近几条消息供 Supervisor 阅读。"""
    lines = []
    for msg in messages[-limit:]:
        role = getattr(msg, "name", None) or msg.__class__.__name__.replace("Message", "")
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        lines.append(f"[{role}]: {content[:400]}")
    return "\n".join(lines) if lines else "(no messages yet)"


def _log_step(state: MultiAgentState, agent: str, output: str, t0: float) -> None:
    """向 agent_log 追加 Worker 执行记录。"""
    state["agent_log"].append({
        "agent": agent,
        "output_preview": output[:300],
        "time_ms": round((time.perf_counter() - t0) * 1000),
    })


def _invoke_sub_agent(name: str, state: MultiAgentState, user_content: str) -> str:
    """调用指定 ReAct 子 Agent，返回最终文本输出。"""
    agent = _get_sub_agent(name, state["scenario"])
    prior = list(state.get("messages", []))
    result = agent.invoke(
        {"messages": prior + [HumanMessage(content=user_content)]},
        config={"recursion_limit": MAX_REACT_ITERATIONS},
    )
    return _last_ai_content(result.get("messages", []))


def _extract_tool_outputs(messages: list[BaseMessage]) -> str:
    """从 ReAct 消息历史中提取工具返回的搜索摘要。"""
    parts = []
    for msg in messages:
        if msg.__class__.__name__ == "ToolMessage":
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            parts.append(content[:500])
    return "\n\n".join(parts)


# ── 规则兜底路由（Supervisor LLM 失败时使用）──────────────────────────────────
def _rule_based_next(state: MultiAgentState) -> str:
    """确定性路由：保证小模型或 Supervisor 异常时流水线仍可推进。"""
    if not state.get("plan"):
        return "planner"
    if not state.get("research"):
        return "researcher"
    if not state.get("content"):
        return "writer"

    last = state.get("last_agent", "")
    critique = state.get("critique") or {}
    revision_count = state.get("revision_count", 0)

    if last == "writer":
        return "critic"

    if last == "critic":
        score = critique.get("overall_score", 10)
        verdict = critique.get("verdict", "pass")
        if verdict == "revise" and score < CRITIC_PASS_SCORE and revision_count < MAX_REVISION_LOOPS:
            return "writer"
        if not state.get("summary"):
            return "summarizer"
        return "FINISH"

    if last == "summarizer" or state.get("summary"):
        return "FINISH"

    if not critique:
        return "critic"
    if not state.get("summary"):
        return "summarizer"
    return "FINISH"


def _validate_next(state: MultiAgentState, proposed: str) -> str:
    """校验 Supervisor 决策，不合法则回退到规则路由。"""
    if proposed not in VALID_NEXT:
        return _rule_based_next(state)
    if proposed == "researcher" and not state.get("plan"):
        return "planner"
    if proposed == "writer" and not state.get("research"):
        return "researcher"
    if proposed == "critic" and not state.get("content"):
        return "writer"
    if proposed == "summarizer" and not state.get("content"):
        return "writer"
    return proposed


# ── Supervisor 节点 ────────────────────────────────────────────────────────────
def node_supervisor(state: MultiAgentState) -> MultiAgentState:
    """
    Supervisor 节点：LLM 动态决定 next_agent，规则兜底 + 最大轮次保护。
    """
    turns = state.get("supervisor_turns", 0) + 1
    state["supervisor_turns"] = turns

    if turns > MAX_SUPERVISOR_TURNS:
        logger.warning("[Supervisor] Max turns reached → FINISH")
        state["next_agent"] = "FINISH"
        return state

    # 首次进入：直接派 Planner，减少一次 LLM 调用
    if turns == 1 and not state.get("plan"):
        state["next_agent"] = "planner"
        logger.info("[Supervisor] Initial → planner")
        return state

    chain = SUPERVISOR_PROMPT | _llm()
    result = chain.invoke({
        "task": state["task"],
        "scenario": state["scenario"],
        "has_plan": bool(state.get("plan")),
        "has_research": bool(state.get("research")),
        "has_content": bool(state.get("content")),
        "has_critique": bool(state.get("critique")),
        "has_summary": bool(state.get("summary")),
        "revision_count": state.get("revision_count", 0),
        "max_revisions": MAX_REVISION_LOOPS,
        "last_agent": state.get("last_agent", "none"),
        "recent_messages": _format_recent_messages(state.get("messages", [])),
    })

    decision = _parse_json(result.content, {"next": _rule_based_next(state)})
    proposed = decision.get("next", decision.get("agent", "")).lower().strip()
    next_agent = _validate_next(state, proposed if proposed in VALID_NEXT else _rule_based_next(state))

    logger.info(f"[Supervisor] → {next_agent} ({decision.get('reason', 'rule/fallback')})")
    state["next_agent"] = next_agent
    return state


def _route_from_supervisor(state: MultiAgentState) -> str:
    """Supervisor 条件边：映射 next_agent 到图节点名或 END。"""
    nxt = state.get("next_agent", "FINISH")
    if nxt == "FINISH":
        return END
    return nxt


# ── Worker 节点（各为独立 ReAct 子 Agent）──────────────────────────────────────
def node_planner(state: MultiAgentState) -> MultiAgentState:
    """Planner ReAct 子 Agent：拆解任务为 JSON 计划。"""
    t0 = time.perf_counter()
    logger.info("[Planner] ReAct sub-agent running...")

    user_msg = f"Task: {state['task']}\nScenario: {state['scenario']}"
    output = _invoke_sub_agent("planner", state, user_msg)

    plan = _parse_json(output, {
        "goal": state["task"],
        "research_questions": [state["task"]],
        "content_sections": ["Overview", "Analysis", "Conclusion"],
        "tone": "professional",
        "target_audience": "general",
    })
    state["plan"] = plan
    state["last_agent"] = "planner"
    state["messages"] = [AIMessage(content=output, name="Planner")]
    _log_step(state, "planner", json.dumps(plan, ensure_ascii=False), t0)
    return state


def node_researcher(state: MultiAgentState) -> MultiAgentState:
    """Researcher ReAct 子 Agent：自主调用搜索工具并综合研究结论。"""
    t0 = time.perf_counter()
    logger.info("[Researcher] ReAct sub-agent running...")

    plan = state.get("plan", {})
    questions = plan.get("research_questions", [state["task"]])
    user_msg = (
        f"Task: {state['task']}\n"
        f"Plan goal: {plan.get('goal', state['task'])}\n"
        f"Research questions:\n" + "\n".join(f"- {q}" for q in questions) + "\n\n"
        "Use your search tools to gather information, then synthesize findings in markdown."
    )

    agent = _get_sub_agent("researcher", state["scenario"])
    prior = list(state.get("messages", []))
    result = agent.invoke(
        {"messages": prior + [HumanMessage(content=user_msg)]},
        config={"recursion_limit": MAX_REACT_ITERATIONS},
    )
    result_messages = result.get("messages", [])
    output = _last_ai_content(result_messages)
    tool_output = _extract_tool_outputs(result_messages)

    state["research"] = output
    state["search_results"] = tool_output or output[:2000]
    state["last_agent"] = "researcher"
    state["messages"] = [AIMessage(content=output, name="Researcher")]
    _log_step(state, "researcher", output, t0)
    return state


def node_writer(state: MultiAgentState) -> MultiAgentState:
    """Writer ReAct 子 Agent：根据 plan + research 撰写正文，可吸收 Critic 反馈修订。"""
    t0 = time.perf_counter()
    logger.info("[Writer] ReAct sub-agent running...")

    plan = state.get("plan", {})
    critique = state.get("critique") or {}
    improvements = critique.get("improvements", [])

    user_msg = (
        f"Task: {state['task']}\n"
        f"Scenario: {state['scenario']}\n"
        f"Tone: {plan.get('tone', 'professional')}\n"
        f"Target audience: {plan.get('target_audience', 'general audience')}\n\n"
        f"Plan:\n{json.dumps(plan, ensure_ascii=False)}\n\n"
        f"Research findings:\n{state.get('research', '')}\n"
    )
    if improvements:
        user_msg += f"\nCritic revision feedback (must address):\n" + "\n".join(f"- {i}" for i in improvements)

    output = _invoke_sub_agent("writer", state, user_msg)
    state["content"] = output
    state["last_agent"] = "writer"
    state["messages"] = [AIMessage(content=output, name="Writer")]
    _log_step(state, "writer", output, t0)
    return state


def node_critic(state: MultiAgentState) -> MultiAgentState:
    """Critic ReAct 子 Agent：评估正文质量，输出 JSON 评分。"""
    t0 = time.perf_counter()
    logger.info("[Critic] ReAct sub-agent running...")

    plan = state.get("plan", {})
    user_msg = (
        f"Goal: {plan.get('goal', state['task'])}\n\n"
        f"Content to evaluate:\n{state.get('content', '')}"
    )
    output = _invoke_sub_agent("critic", state, user_msg)

    critique = _parse_json(output, {
        "overall_score": 8, "verdict": "pass",
        "strengths": [], "improvements": [],
        "scores": {"accuracy": 8, "clarity": 8, "relevance": 8, "actionability": 8},
    })
    state["critique"] = critique
    state["revision_count"] = state.get("revision_count", 0) + 1
    state["last_agent"] = "critic"
    state["messages"] = [AIMessage(content=output, name="Critic")]
    _log_step(state, "critic", json.dumps(critique, ensure_ascii=False), t0)
    return state


def node_summarizer(state: MultiAgentState) -> MultiAgentState:
    """Summarizer ReAct 子 Agent：生成执行摘要并组装 final_output。"""
    t0 = time.perf_counter()
    logger.info("[Summarizer] ReAct sub-agent running...")

    user_msg = f"Content:\n{state.get('content', '')}"
    output = _invoke_sub_agent("summarizer", state, user_msg)

    state["summary"] = output
    state["final_output"] = f"{state['content']}\n\n---\n\n## Executive Summary\n{output}"
    state["last_agent"] = "summarizer"
    state["messages"] = [AIMessage(content=output, name="Summarizer")]
    _log_step(state, "summarizer", output, t0)
    return state


# ── 构建状态图 ─────────────────────────────────────────────────────────────────
def build_graph():
    """
    Supervisor + ReAct Workers 拓扑:

        supervisor ──(动态)──→ planner | researcher | writer | critic | summarizer | END
        各 worker ──→ supervisor（汇报后等待下一派活）
    """
    g = StateGraph(MultiAgentState)
    g.add_node("supervisor", node_supervisor)
    g.add_node("planner", node_planner)
    g.add_node("researcher", node_researcher)
    g.add_node("writer", node_writer)
    g.add_node("critic", node_critic)
    g.add_node("summarizer", node_summarizer)

    g.set_entry_point("supervisor")
    g.add_conditional_edges("supervisor", _route_from_supervisor, {
        "planner": "planner",
        "researcher": "researcher",
        "writer": "writer",
        "critic": "critic",
        "summarizer": "summarizer",
        END: END,
    })
    for worker in WORKER_AGENTS:
        g.add_edge(worker, "supervisor")

    return g.compile()


_graph = None


def get_graph():
    """获取已编译图的懒加载单例。"""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _initial_state(task: str, scenario: str) -> MultiAgentState:
    """构造流水线初始状态。"""
    return {
        "task": task,
        "scenario": scenario,
        "messages": [HumanMessage(content=f"Task: {task}\nScenario: {scenario}")],
        "next_agent": "planner",
        "last_agent": "",
        "supervisor_turns": 0,
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


# ── 对外 API ───────────────────────────────────────────────────────────────────
def run(task: str, scenario: str = SCENARIO_MARKET_RESEARCH) -> dict:
    """同步执行 Supervisor + ReAct 多 Agent 流水线。"""
    t0 = time.perf_counter()
    result = get_graph().invoke(_initial_state(task, scenario))
    result["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return result


def run_stream(task: str, scenario: str = SCENARIO_MARKET_RESEARCH) -> Generator[dict, None, None]:
    """流式执行，每完成一个 Worker 节点 yield 进度事件（跳过 Supervisor）。"""
    t0 = time.perf_counter()
    for event in get_graph().stream(_initial_state(task, scenario), stream_mode="updates"):
        for node_name, node_state in event.items():
            if node_name == "supervisor":
                continue
            log = node_state.get("agent_log", [])
            last = log[-1] if log else {}
            yield {
                "type": "node_complete",
                "agent": node_name,
                "preview": last.get("output_preview", ""),
                "time_ms": last.get("time_ms", 0),
            }

    yield {"type": "done", "total_latency_ms": round((time.perf_counter() - t0) * 1000)}


# ── 兼容旧测试的辅助函数 ───────────────────────────────────────────────────────
def _route_after_critic(state: MultiAgentState) -> str:
    """兼容 v2 测试：根据 critique 判断 writer 修订或 summarizer。"""
    score = state.get("critique", {}).get("overall_score", 10)
    verdict = state.get("critique", {}).get("verdict", "pass")
    if verdict == "pass" or score >= CRITIC_PASS_SCORE or state.get("revision_count", 0) >= MAX_REVISION_LOOPS:
        return "summarizer"
    return "writer"
