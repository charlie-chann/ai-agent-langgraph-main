"""Project 27 - 热点追踪 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import run_track_topic, run_batch_track, run_get_trending, stream_chat
from config import HEAT_LEVELS, ALERT_THRESHOLD

st.set_page_config(
    page_title="🔥 热点追踪 Agent",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# 🔥 热点追踪 Agent")
    st.caption("OpenClaw 内容管道 · Project 27")
    st.divider()
    tab_choice = st.radio(
        "功能",
        ["📊 单话题追踪", "⚡ 热门排行", "💬 AI 分析"],
        label_visibility="collapsed"
    )
    st.divider()
    custom_topics = st.text_area("自定义追踪话题（每行一个）", placeholder="AI科技\n量子计算\n马斯克", height=100)
    st.divider()
    st.caption("热度预警阈值: " + f"{ALERT_THRESHOLD:.0%}")
    st.caption("OpenClaw · Ollama qwen3.5")


def _heat_badge(level: str) -> str:
    return {"cold": "🔵 冷", "warming": "🟡 升温", "hot": "🟠 热门", "trending": "🔴 爆发"}.get(level, "⚪ 未知")


if tab_choice == "📊 单话题追踪":
    st.title("📊 话题热度追踪")
    st.caption("实时分析话题在各平台的热度状态与内容创作机会")

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("追踪话题", placeholder="输入话题关键词…")
    with col2:
        st.write("")
        st.write("")
        track_btn = st.button("🔍 追踪", type="primary", use_container_width=True)

    if track_btn and topic:
        with st.spinner("正在多平台检测热度…"):
            result = run_track_topic(topic.strip())

        if result["success"]:
            report = result["report"]
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("热度状态", _heat_badge(result["heat_level"]))
            col_b.metric("热度分数", f"{result['heat_score']:.0%}")
            col_c.metric("动量趋势", f"{'↑' if report.momentum > 0 else '↓'} {abs(report.momentum):.1%}")
            col_d.metric("预警触发", "🚨 是" if result["alert"] else "✅ 否")

            st.divider()
            st.subheader("📡 各平台信号")
            for s in report.top_signals:
                with st.expander(f"{s.source} — 热度 {s.heat_score:.0%}"):
                    st.write(f"**关键词**: {s.keyword} | **提及次数**: {s.mentions}")
                    st.write(f"**动量**: {'+' if s.momentum > 0 else ''}{s.momentum:.1%}")

            st.divider()
            st.subheader("💡 内容创作机会")
            for opp in result["opportunities"]:
                st.write("•", opp)

            st.divider()
            st.subheader("📅 建议发布日历")
            calendar = result.get("calendar", [])
            if calendar:
                import pandas as pd
                df = pd.DataFrame(calendar)
                st.dataframe(df, use_container_width=True)
        else:
            st.error(result.get("error"))

elif tab_choice == "⚡ 热门排行":
    st.title("⚡ 当前热门话题排行")
    st.caption("基于配置的追踪话题，按热度排序")

    topics = []
    if custom_topics:
        topics = [t.strip() for t in custom_topics.split("\n") if t.strip()]

    if st.button("🔄 刷新排行", type="primary"):
        with st.spinner("分析中…"):
            results = run_get_trending(top_n=10) if not topics else run_batch_track(topics)

        for i, r in enumerate(results[:10], 1):
            if r.get("success"):
                cols = st.columns([1, 3, 2, 2, 2])
                cols[0].write(f"**#{i}**")
                cols[1].write(r["report"].topic)
                cols[2].write(_heat_badge(r["heat_level"]))
                cols[3].progress(r["heat_score"])
                cols[4].write("🚨" if r["alert"] else "")

elif tab_choice == "💬 AI 分析":
    st.title("💬 趋势分析师")
    if "messages_27" not in st.session_state:
        st.session_state.messages_27 = []
    for msg in st.session_state.messages_27:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("问关于话题热点的问题…"):
        st.session_state.messages_27.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            container = st.empty()
            full = ""
            try:
                for chunk in stream_chat(prompt):
                    full += chunk
                    container.markdown(full + "▌")
                container.markdown(full)
            except Exception as e:
                container.error(str(e))
                full = str(e)
        st.session_state.messages_27.append({"role": "assistant", "content": full})
