"""
agent.py — 多 Agent 协作系统 (LangGraph) v2.0

【职责】
1. 定义 MultiAgentState 共享状态，承载 Planner → Researcher → Writer → Critic → Summarizer 流水线数据
2. 实现各 Agent 节点函数与 Critic 后的条件路由（通过则 Summarizer，否则回 Writer 修订）
3. 编译 LangGraph 状态图，对外提供 run / run_stream 同步与流式 API

【设计原因】
1. LangGraph StateGraph：显式 DAG + 条件边，比手写循环更易扩展节点与观测
2. Critic 修订环路上限 MAX_REVISION_LOOPS：防止低分内容无限重写，控制延迟与成本
3. LLM 分 creative / 非 creative 两档温度：规划/评审偏确定性，写作偏创意
4. JSON 解析 fallback（正则提取 + 默认 plan/critique）：小模型输出不规范时不致崩溃
5. 图单例 get_graph()：避免重复 compile；agent_log 记录每步耗时供 UI 时间线展示
"""
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


# ── 共享状态 ───────────────────────────────────────────────────────────────────
class MultiAgentState(TypedDict):
    """
    LangGraph 各节点读写的全局状态字典。

    字段说明:
        task: 用户原始任务描述
        scenario: 业务场景（market_research / social_media）
        plan: Planner 输出的 JSON 计划
        search_results: multi_search 原始检索文本
        research: Researcher 综合后的 Markdown 研究结论
        content: Writer 产出的正文
        critique: Critic 输出的 JSON 评分与修订建议
        summary: Summarizer 生成的执行摘要
        revision_count: Critic 已执行次数（含首次评估）
        agent_log: 每步 agent 名、输出预览、耗时(ms)
        final_output: 正文 + 分隔线 + Executive Summary 的完整交付物
        total_latency_ms: 整链端到端耗时（由 run/run_stream 填充）
    """
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
    """
    创建 Ollama Chat 模型实例。

    参数:
        creative: True 时使用 CREATIVE_TEMPERATURE（写作节点）；否则 TEMPERATURE（规划/评审）

    返回:
        配置好 base_url、model、temperature 的 ChatOllama 实例
    """
    return ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=CREATIVE_TEMPERATURE if creative else TEMPERATURE,
    )


def _log_step(state: MultiAgentState, agent: str, output: str, t0: float) -> None:
    """
    向 state["agent_log"] 追加一步执行记录。

    参数:
        state: 当前图状态
        agent: 节点名称（planner / researcher / ...）
        output: 该步主要输出（截断前 300 字符作为 preview）
        t0: perf_counter 起始时间，用于计算 time_ms
    """
    state["agent_log"].append({
        "agent": agent,
        "output_preview": output[:300],
        "time_ms": round((time.perf_counter() - t0) * 1000),
    })


# ── Agent 节点 ─────────────────────────────────────────────────────────────────
def node_planner(state: MultiAgentState) -> MultiAgentState:
    """
    Planner 节点：将用户任务拆解为结构化 JSON 计划。

    流程:
        1. PLANNER_PROMPT | LLM 调用
        2. 解析 JSON；失败则用正则提取或 fallback 默认 plan
        3. 写入 state["plan"] 并记录 agent_log
    """
    t0 = time.perf_counter()
    logger.info("[Planner] Planning task...")
    chain = PLANNER_PROMPT | _llm()
    result = chain.invoke({"task": state["task"], "scenario": state["scenario"]})

    try:
        plan = json.loads(result.content)
    except json.JSONDecodeError:
        # 小模型常在 JSON 外包裹说明文字，用正则兜底提取 {...}
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
    """
    Researcher 节点：按计划中的 research_questions 搜索并 synthesize 研究结论。

    流程:
        1. multi_search 批量检索 → search_results
        2. RESEARCHER_PROMPT | LLM 综合为 Markdown → research
    """
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
    """
    Writer 节点：根据 scenario 选择市场调研或社媒 Prompt 生成正文。

    流程:
        1. social_media → WRITER_SOCIAL_PROMPT；否则 WRITER_MARKET_PROMPT
        2. creative=True 提升文案多样性
        3. 修订环中 Critic 打回后会再次进入此节点重写 content
    """
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
    """
    Critic 节点：对 Writer 产出打分，决定 pass 或 revise。

    流程:
        1. CRITIC_PROMPT | LLM 输出 JSON critique
        2. 解析失败时 fallback 默认 pass 结构
        3. revision_count 自增，供路由与 UI 展示修订次数
    """
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
    """
    Summarizer 节点：生成执行摘要并组装 final_output。

    流程:
        1. SUMMARIZER_PROMPT | LLM 生成 summary
        2. final_output = content + 分隔线 + Executive Summary 标题 + summary
    """
    t0 = time.perf_counter()
    logger.info("[Summarizer] Creating summary...")
    chain = SUMMARIZER_PROMPT | _llm()
    result = chain.invoke({"content": state["content"]})
    state["summary"] = result.content
    state["final_output"] = f"{state['content']}\n\n---\n\n## Executive Summary\n{result.content}"
    _log_step(state, "Summarizer", result.content, t0)
    return state


# ── 条件路由 ───────────────────────────────────────────────────────────────────
def _route_after_critic(state: MultiAgentState) -> str:
    """
    Critic 之后的条件边：决定进入 summarizer 或回 writer 修订。

    通过条件（任一满足即 summarizer）:
        - verdict == "pass"
        - overall_score >= CRITIC_PASS_SCORE
        - revision_count >= MAX_REVISION_LOOPS（防止无限循环）

    返回:
        "summarizer" 或 "writer"（与 add_conditional_edges 映射键一致）
    """
    score = state["critique"].get("overall_score", 10)
    verdict = state["critique"].get("verdict", "pass")
    if verdict == "pass" or score >= CRITIC_PASS_SCORE or state["revision_count"] >= MAX_REVISION_LOOPS:
        logger.info(f"[Critic] Score={score} → Summarizer")
        return "summarizer"
    logger.info(f"[Critic] Score={score} → revise (loop {state['revision_count']})")
    return "writer"


# ── 构建状态图 ─────────────────────────────────────────────────────────────────
def build_graph():
    """
    构建并编译 LangGraph 多 Agent 流水线。

    拓扑:
        planner → researcher → writer → critic
        critic ──(条件)──→ writer（修订）或 summarizer → END

    返回:
        已 compile 的可 invoke/stream 的图对象
    """
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


# 进程级图单例，首次 invoke 时 compile
_graph = None


def get_graph():
    """
    获取已编译图的懒加载单例。

    返回:
        compile 后的 StateGraph 实例
    """
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


# ── 对外 API ───────────────────────────────────────────────────────────────────
def run(task: str, scenario: str = SCENARIO_MARKET_RESEARCH) -> dict:
    """
    同步执行完整多 Agent 流水线。

    参数:
        task: 用户任务描述
        scenario: 业务场景，默认市场调研

    返回:
        执行完毕的 MultiAgentState 字典（含 total_latency_ms）
    """
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
    """
    流式执行流水线，每完成一个节点 yield 进度事件。

    参数:
        task: 用户任务描述
        scenario: 业务场景

    Yields:
        {"type": "node_complete", "agent", "preview", "time_ms"} 各节点完成时
        {"type": "done", "total_latency_ms"} 全部结束时

    说明:
        stream_mode="updates" 仅推送有变化的节点状态，便于 UI 逐步更新进度条
    """
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
