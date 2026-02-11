"""
app.py — Multi-Agent 协作系统 Streamlit 前端

【职责】
1. 提供侧边栏配置（模型名、场景、示例任务）与主流水线进度可视化
2. 调用 run_stream 实时更新五 Agent 状态，再 run 拉取完整 state 展示报告与评分
3. 支持历史记录、Critique 明细、Agent Log 时间线与 Markdown 下载

【设计原因】
1. 先 stream 后 sync run：stream 仅推送节点进度，完整 state 需 invoke 一次拿全量字段（content/critique）
2. session_state.history：跨 rerun 保留最近运行记录，示例按钮通过 prefill 注入任务框
3. 五列 progress_cols 与 AGENT_ICONS 映射：用户直观看到 Planner→Summarizer 流水线
4. expander 分层展示：正文 / 摘要 / 评分 / 日志互不干扰，默认展开核心内容
"""
import json
import time
import streamlit as st

# 页面配置需在其它 st 组件之前调用
st.set_page_config(
    page_title="Multi-Agent Collaboration",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import (
    DEFAULT_MODEL, OLLAMA_BASE_URL,
    SCENARIO_MARKET_RESEARCH, SCENARIO_SOCIAL_MEDIA,
    MAX_REVISION_LOOPS, CRITIC_PASS_SCORE,
)
from agent import run_stream, run

# ── Session 初始化 ────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

# 各 Agent 节点在 UI 中的图标与显示名称
AGENT_ICONS = {
    "planner":    "🗺️",
    "researcher": "🔍",
    "writer":     "✍️",
    "critic":     "🎯",
    "summarizer": "📋",
}

AGENT_LABELS = {
    "planner":    "Planner",
    "researcher": "Researcher",
    "writer":     "Writer",
    "critic":     "Critic",
    "summarizer": "Summarizer",
}

# 按场景预置示例任务，侧边栏一键填入
SCENARIO_EXAMPLES = {
    SCENARIO_MARKET_RESEARCH: [
        "AI agent market in 2025: size, key players, growth trends",
        "Electric vehicle market in California: opportunities and competitive landscape",
        "Enterprise SaaS security tools: market analysis and top vendors",
    ],
    SCENARIO_SOCIAL_MEDIA: [
        "Announce our new AI-powered RAG product launch targeting CTOs",
        "Share insights about why local AI models are better for privacy-conscious enterprises",
        "Promote our LangChain-based multi-agent platform to developers",
    ],
}

# ── 侧边栏 ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤝 Multi-Agent System")
    st.caption("Planner · Researcher · Writer · Critic · Summarizer")
    st.divider()

    st.markdown("### ⚙️ Settings")
    model = st.text_input("Ollama Model", value=DEFAULT_MODEL)
    scenario = st.selectbox(
        "Scenario",
        options=[SCENARIO_MARKET_RESEARCH, SCENARIO_SOCIAL_MEDIA],
        format_func=lambda x: "📊 Market Research Report" if x == SCENARIO_MARKET_RESEARCH else "📱 Social Media Content",
    )

    st.divider()
    st.markdown("### 💡 Example Tasks")
    for ex in SCENARIO_EXAMPLES[scenario]:
        if st.button(f"▶ {ex[:50]}...", key=ex):
            # 写入 prefill，主区域 text_area 在下次 render 时 pop 填入
            st.session_state["prefill"] = ex

    st.divider()
    st.markdown("### 🤖 Agent Pipeline")
    pipeline = ["🗺️ Planner", "🔍 Researcher", "✍️ Writer", "🎯 Critic", "📋 Summarizer"]
    for step in pipeline:
        st.markdown(f"  {step}")
    st.caption(f"Max revisions: {MAX_REVISION_LOOPS}  ·  Pass score: {CRITIC_PASS_SCORE}/10")

    if st.button("🗑️ Clear history"):
        st.session_state.history = []
        st.rerun()

# ── 主区域 ─────────────────────────────────────────────────────────────────────
st.markdown("# 🤝 Multi-Agent Collaboration System")
st.caption(
    f"**{'Market Research' if scenario == SCENARIO_MARKET_RESEARCH else 'Social Media'}** scenario  ·  "
    f"{model} @ {OLLAMA_BASE_URL}"
)

if st.session_state.history:
    with st.expander(f"📜 History ({len(st.session_state.history)} runs)", expanded=False):
        for i, h in enumerate(reversed(st.session_state.history[-5:]), 1):
            st.markdown(f"**{i}.** `{h['task'][:60]}` — {h['total_ms']}ms")

default_task = st.session_state.pop("prefill", "")
task = st.text_area(
    "Enter your task",
    value=default_task,
    height=80,
    placeholder="e.g. AI agent market in 2025: size, key players, growth trends",
)

col1, col2 = st.columns([1, 5])
with col1:
    run_btn = st.button("🚀 Run", type="primary", disabled=not task.strip())

if run_btn and task.strip():
    st.divider()

    # ── Agent 进度条：五列对应五个节点 ───────────────────────────────────────
    progress_cols = st.columns(5)
    agent_status = {a: "⏳" for a in AGENT_ICONS}
    agent_placeholders = {}
    for i, (agent, icon) in enumerate(AGENT_ICONS.items()):
        with progress_cols[i]:
            agent_placeholders[agent] = {
                "icon": st.empty(),
                "time": st.empty(),
            }
            agent_placeholders[agent]["icon"].markdown(f"### {icon}\n**{AGENT_LABELS[agent]}**\n⏳")

    st.divider()
    output_placeholder = st.empty()
    critique_placeholder = st.empty()
    summary_placeholder = st.empty()

    final_state = None

    # 第一阶段：流式更新各 Agent 完成状态与耗时
    with st.spinner("Multi-agent pipeline running..."):
        for event in run_stream(task.strip(), scenario):
            if event["type"] == "node_complete":
                agent = event["agent"]
                ms = event.get("time_ms", 0)
                agent_placeholders[agent]["icon"].markdown(
                    f"### {AGENT_ICONS.get(agent, '🤖')}\n**{AGENT_LABELS.get(agent, agent)}**\n✅ {ms}ms"
                )

            elif event["type"] == "done":
                pass

    # 第二阶段：非流式 run 获取完整 state（stream 的 updates 不含全部字段）
    with st.spinner("Fetching full output..."):
        final_state = run(task.strip(), scenario)

    if final_state:
        # ── 质量指标卡片 ─────────────────────────────────────────────────────
        critique = final_state.get("critique", {})
        score = critique.get("overall_score", "—")
        verdict = critique.get("verdict", "—")
        revisions = final_state.get("revision_count", 0)

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Quality Score", f"{score}/10")
        col_m2.metric("Verdict", f"{'✅ Pass' if verdict == 'pass' else '⚠️ Revised'}")
        col_m3.metric("Revisions", revisions)
        col_m4.metric("Total Time", f"{final_state.get('total_latency_ms', 0)}ms")

        # ── 正文 ─────────────────────────────────────────────────────────────
        with st.expander("📝 Full Report / Content", expanded=True):
            st.markdown(final_state.get("content", ""))

        # ── 执行摘要 ─────────────────────────────────────────────────────────
        if final_state.get("summary"):
            with st.expander("📋 Executive Summary", expanded=True):
                st.markdown(final_state["summary"])

        # ── Critic 评分明细 ──────────────────────────────────────────────────
        if critique:
            with st.expander("🎯 Critic Evaluation"):
                if "scores" in critique:
                    scores = critique["scores"]
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric("Accuracy", f"{scores.get('accuracy', '—')}/10")
                    sc2.metric("Clarity", f"{scores.get('clarity', '—')}/10")
                    sc3.metric("Relevance", f"{scores.get('relevance', '—')}/10")
                    sc4.metric("Actionability", f"{scores.get('actionability', '—')}/10")
                if critique.get("strengths"):
                    st.markdown("**Strengths:**")
                    for s in critique["strengths"]:
                        st.markdown(f"  ✓ {s}")
                if critique.get("improvements"):
                    st.markdown("**Improvements:**")
                    for imp in critique["improvements"]:
                        st.markdown(f"  → {imp}")

        # ── Agent 流水线日志时间线 ───────────────────────────────────────────
        with st.expander("🔄 Agent Pipeline Log"):
            for step in final_state.get("agent_log", []):
                agent = step["agent"]
                icon = AGENT_ICONS.get(agent, "🤖")
                st.markdown(f"**{icon} {AGENT_LABELS.get(agent, agent)}** — {step['time_ms']}ms")
                st.text(step["output_preview"][:200])
                st.divider()

        # ── Markdown 下载 ────────────────────────────────────────────────────
        st.download_button(
            label="⬇️ Download Output",
            data=final_state.get("final_output", ""),
            file_name=f"output_{scenario}_{int(time.time())}.md",
            mime="text/markdown",
        )

        # 写入 session 历史，供侧边栏 History expander 展示
        st.session_state.history.append({
            "task": task,
            "scenario": scenario,
            "total_ms": final_state.get("total_latency_ms", 0),
        })
