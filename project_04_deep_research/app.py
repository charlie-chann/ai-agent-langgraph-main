# app.py — Streamlit UI for Deep Research Agent
import time
import streamlit as st

st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, MAX_SEARCH_ROUNDS, SEARCHES_PER_ROUND
from agent import research_stream, research

# ── Session state ─────────────────────────────────────────────────────────────
if "reports" not in st.session_state:
    st.session_state.reports = []

STEP_ICONS = {
    "generate_queries": "🎯",
    "search":           "🔍",
    "synthesize":       "📖",
    "gap_analysis":     "🕵️",
    "write_report":     "✍️",
    "polish_report":    "✨",
}

STEP_LABELS = {
    "generate_queries": "Query Generator",
    "search":           "Web Searcher",
    "synthesize":       "Synthesizer",
    "gap_analysis":     "Gap Analyzer",
    "write_report":     "Report Writer",
    "polish_report":    "Report Polisher",
}

EXAMPLE_TOPICS = [
    "AI agent market 2025: size, key players, growth trends",
    "Impact of local LLMs on enterprise data privacy",
    "LangChain vs LlamaIndex: technical comparison and use cases",
    "Electric vehicle adoption in California 2024-2026",
    "Generative AI in financial services: opportunities and risks",
]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 Deep Research Agent")
    st.caption("Iterative Search · Gap Analysis · Auto-polish Report")
    st.divider()

    st.markdown("### ⚙️ Settings")
    st.text_input("Model", value=DEFAULT_MODEL)
    st.metric("Max Search Rounds", MAX_SEARCH_ROUNDS)
    st.metric("Searches per Round", SEARCHES_PER_ROUND)

    st.divider()
    st.markdown("### 📚 Pipeline")
    for node, label in STEP_LABELS.items():
        st.markdown(f"  {STEP_ICONS[node]} {label}")

    st.divider()
    st.markdown("### 💡 Example Topics")
    for ex in EXAMPLE_TOPICS:
        if st.button(ex[:45] + ("..." if len(ex) > 45 else ""), key=ex):
            st.session_state["prefill"] = ex

    if st.session_state.reports:
        st.divider()
        st.markdown(f"### 📄 Reports ({len(st.session_state.reports)})")
        for r in reversed(st.session_state.reports[-3:]):
            st.caption(r["topic"][:40])

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# 🔬 Deep Research Agent")
st.caption(
    f"Iterative search → synthesis → gap analysis → report writing  ·  "
    f"**{DEFAULT_MODEL}** @ {OLLAMA_BASE_URL}"
)

prefill = st.session_state.pop("prefill", "")
topic = st.text_input(
    "Research Topic",
    value=prefill,
    placeholder="e.g. AI agent market in 2025: key players, market size, growth trends",
)

col1, col2 = st.columns([1, 6])
with col1:
    start = st.button("🚀 Start Research", type="primary", disabled=not topic.strip())

if start and topic.strip():
    st.divider()

    # Progress tracker
    progress_cols = st.columns(len(STEP_LABELS))
    step_placeholders = {}
    for i, (node, label) in enumerate(STEP_LABELS.items()):
        with progress_cols[i]:
            step_placeholders[node] = st.empty()
            step_placeholders[node].markdown(f"**{STEP_ICONS[node]}**\n{label}\n⏳")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # Research notes live display
    notes_expander = st.expander("📖 Live Research Notes", expanded=False)
    notes_placeholder = notes_expander.empty()

    st.divider()
    report_placeholder = st.empty()

    step_order = list(STEP_LABELS.keys())
    completed_steps = []

    with st.spinner("Deep research in progress..."):
        for event in research_stream(topic.strip()):
            if event["type"] == "step":
                node = event["node"]
                ms = event.get("time_ms", 0)
                score = event.get("coverage_score", None)
                round_num = event.get("round", None)

                step_placeholders[node].markdown(
                    f"**{STEP_ICONS.get(node, '🤖')}**\n{STEP_LABELS.get(node, node)}\n✅ {ms}ms"
                )
                completed_steps.append(node)
                progress = len(set(completed_steps)) / len(step_order)
                progress_bar.progress(min(progress, 1.0))

                label = STEP_LABELS.get(node, node)
                if score is not None:
                    status_text.markdown(f"**{label}** completed — Coverage: {score:.0%}  Round: {round_num}/{MAX_SEARCH_ROUNDS}")
                else:
                    status_text.markdown(f"**{label}** completed ({ms}ms)")

            elif event["type"] == "done":
                progress_bar.progress(1.0)
                status_text.markdown(f"✅ Research complete! Total: {event['total_latency_ms']}ms")

    # Final result
    with st.spinner("Loading final report..."):
        final = research(topic.strip())

    progress_bar.progress(1.0)

    if final:
        # Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Search Rounds", final.get("round", 0))
        m2.metric("Total Queries", len(final.get("all_queries", [])))
        m3.metric("Coverage", f"{final.get('coverage_score', 0):.0%}")
        m4.metric("Total Time", f"{final.get('total_latency_ms', 0) // 1000}s")

        # Report display
        report = final.get("final_report", final.get("report_draft", "No report generated."))
        with st.expander("📊 Full Research Report", expanded=True):
            st.markdown(report)

        # Research notes
        with st.expander("📖 Research Notes"):
            st.markdown(final.get("research_notes", ""))

        # Gap analysis
        gap = final.get("gap_analysis", {})
        if gap:
            with st.expander("🕵️ Final Gap Analysis"):
                st.metric("Coverage Score", f"{gap.get('coverage_score', 0):.0%}")
                if gap.get("well_covered"):
                    st.markdown("**Well covered:**")
                    for item in gap["well_covered"]:
                        st.markdown(f"  ✓ {item}")
                if gap.get("gaps"):
                    st.markdown("**Remaining gaps:**")
                    for item in gap["gaps"]:
                        st.markdown(f"  △ {item}")

        # Step timeline
        with st.expander("🔄 Research Timeline"):
            for step in final.get("step_log", []):
                icon = STEP_ICONS.get(step["step"].split()[0].lower().replace(" ", "_"), "📌")
                st.markdown(f"**{icon} {step['step']}** — {step['time_ms']}ms")
                if step.get("preview"):
                    st.text(step["preview"][:150])
                st.divider()

        # Saved path
        if final.get("saved_path"):
            st.success(f"Report saved: `{final['saved_path']}`")

        # Download
        st.download_button(
            "⬇️ Download Report (.md)",
            data=report,
            file_name=f"research_{topic[:30].replace(' ', '_')}.md",
            mime="text/markdown",
        )

        st.session_state.reports.append({
            "topic": topic,
            "rounds": final.get("round", 0),
            "coverage": final.get("coverage_score", 0),
        })
