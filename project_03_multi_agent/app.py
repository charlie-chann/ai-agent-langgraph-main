# app.py — Streamlit UI for Multi-Agent Collaboration System
import json
import time
import streamlit as st

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

# ── Session init ──────────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

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

# ── Sidebar ───────────────────────────────────────────────────────────────────
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

# ── Main ──────────────────────────────────────────────────────────────────────
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

    # Agent progress display
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

    # Re-run non-streaming to get full state for display
    with st.spinner("Fetching full output..."):
        final_state = run(task.strip(), scenario)

    if final_state:
        # Critique score
        critique = final_state.get("critique", {})
        score = critique.get("overall_score", "—")
        verdict = critique.get("verdict", "—")
        revisions = final_state.get("revision_count", 0)

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Quality Score", f"{score}/10")
        col_m2.metric("Verdict", f"{'✅ Pass' if verdict == 'pass' else '⚠️ Revised'}")
        col_m3.metric("Revisions", revisions)
        col_m4.metric("Total Time", f"{final_state.get('total_latency_ms', 0)}ms")

        # Main content
        with st.expander("📝 Full Report / Content", expanded=True):
            st.markdown(final_state.get("content", ""))

        # Summary
        if final_state.get("summary"):
            with st.expander("📋 Executive Summary", expanded=True):
                st.markdown(final_state["summary"])

        # Critique details
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

        # Agent log timeline
        with st.expander("🔄 Agent Pipeline Log"):
            for step in final_state.get("agent_log", []):
                agent = step["agent"]
                icon = AGENT_ICONS.get(agent, "🤖")
                st.markdown(f"**{icon} {AGENT_LABELS.get(agent, agent)}** — {step['time_ms']}ms")
                st.text(step["output_preview"][:200])
                st.divider()

        # Download button
        st.download_button(
            label="⬇️ Download Output",
            data=final_state.get("final_output", ""),
            file_name=f"output_{scenario}_{int(time.time())}.md",
            mime="text/markdown",
        )

        st.session_state.history.append({
            "task": task,
            "scenario": scenario,
            "total_ms": final_state.get("total_latency_ms", 0),
        })
