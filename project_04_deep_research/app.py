"""
app.py — Deep Research Agent Streamlit 交互界面

【职责】
提供可视化研究入口：主题输入、流水线步骤进度、指标展示、报告下载与历史摘要。

【设计原因】
Streamlit 快速搭建演示 UI，research_stream 驱动实时步骤反馈；
最终再调用 research() 获取完整状态（流式模式仅推送增量 updates）。
"""
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

# ── 会话状态 ──────────────────────────────────────────────────────────────────
if "reports" not in st.session_state:
    st.session_state.reports = []

# 各 LangGraph 节点对应的 UI 图标与展示标签
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

# 侧边栏示例主题，降低用户冷启动成本
EXAMPLE_TOPICS = [
    "AI agent market 2025: size, key players, growth trends",
    "Impact of local LLMs on enterprise data privacy",
    "LangChain vs LlamaIndex: technical comparison and use cases",
    "Electric vehicle adoption in California 2024-2026",
    "Generative AI in financial services: opportunities and risks",
]

# ── 侧边栏 ───────────────────────────────────────────────────────────────────
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
        # 点击示例将主题写入 session，主区域 text_input 通过 prefill 读取
        if st.button(ex[:45] + ("..." if len(ex) > 45 else ""), key=ex):
            st.session_state["prefill"] = ex

    if st.session_state.reports:
        st.divider()
        st.markdown(f"### 📄 Reports ({len(st.session_state.reports)})")
        for r in reversed(st.session_state.reports[-3:]):
            st.caption(r["topic"][:40])

# ── 主区域 ────────────────────────────────────────────────────────────────────
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

    # 顶部流水线步骤指示器：每列对应一个节点，初始为等待态
    progress_cols = st.columns(len(STEP_LABELS))
    step_placeholders = {}
    for i, (node, label) in enumerate(STEP_LABELS.items()):
        with progress_cols[i]:
            step_placeholders[node] = st.empty()
            step_placeholders[node].markdown(f"**{STEP_ICONS[node]}**\n{label}\n⏳")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # 可折叠的实时研究笔记区域（流式阶段占位，最终由 research() 填充）
    notes_expander = st.expander("📖 Live Research Notes", expanded=False)
    notes_placeholder = notes_expander.empty()

    st.divider()
    report_placeholder = st.empty()

    step_order = list(STEP_LABELS.keys())
    completed_steps = []

    with st.spinner("Deep research in progress..."):
        # 消费 SSE 风格事件，逐步更新步骤 UI
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
                # 按已完成的不重复节点数估算总进度（多轮时同一节点会多次完成）
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

    # 流式结束后同步 invoke 一次，获取完整 final_report 与 step_log
    with st.spinner("Loading final report..."):
        final = research(topic.strip())

    progress_bar.progress(1.0)

    if final:
        # 关键指标四列展示
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Search Rounds", final.get("round", 0))
        m2.metric("Total Queries", len(final.get("all_queries", [])))
        m3.metric("Coverage", f"{final.get('coverage_score', 0):.0%}")
        m4.metric("Total Time", f"{final.get('total_latency_ms', 0) // 1000}s")

        # 最终报告 Markdown 渲染
        report = final.get("final_report", final.get("report_draft", "No report generated."))
        with st.expander("📊 Full Research Report", expanded=True):
            st.markdown(report)

        with st.expander("📖 Research Notes"):
            st.markdown(final.get("research_notes", ""))

        # 最后一轮缺口分析详情
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

        # 各步骤耗时与输出预览时间线
        with st.expander("🔄 Research Timeline"):
            for step in final.get("step_log", []):
                icon = STEP_ICONS.get(step["step"].split()[0].lower().replace(" ", "_"), "📌")
                st.markdown(f"**{icon} {step['step']}** — {step['time_ms']}ms")
                if step.get("preview"):
                    st.text(step["preview"][:150])
                st.divider()

        if final.get("saved_path"):
            st.success(f"Report saved: `{final['saved_path']}`")

        # 浏览器端下载 Markdown 文件
        st.download_button(
            "⬇️ Download Report (.md)",
            data=report,
            file_name=f"research_{topic[:30].replace(' ', '_')}.md",
            mime="text/markdown",
        )

        # 写入会话历史，供侧边栏展示最近报告
        st.session_state.reports.append({
            "topic": topic,
            "rounds": final.get("round", 0),
            "coverage": final.get("coverage_score", 0),
        })
