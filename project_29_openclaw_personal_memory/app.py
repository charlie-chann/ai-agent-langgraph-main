"""Project 29 - 个人记忆 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import run_remember, run_recall, run_forget, run_update, run_list_memories, run_get_stats, stream_chat
from config import MEMORY_TYPES, IMPORTANCE_LEVELS

st.set_page_config(
    page_title="🧠 个人记忆 Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# 🧠 个人记忆 Agent")
    st.caption("OpenClaw 核心能力 · Project 29")
    st.divider()
    tab_choice = st.radio(
        "功能",
        ["📝 记录记忆", "🔍 召回记忆", "📚 记忆库", "📊 统计", "💬 AI 助手"],
        label_visibility="collapsed"
    )
    st.divider()
    # Stats
    stats = run_get_stats()
    st.metric("记忆总数", stats["total"])
    st.metric("存储占用", stats["capacity_used"])
    st.caption("OpenClaw · Ollama qwen3.5")

IMPORTANCE_EMOJI = {"low": "⚪", "medium": "🔵", "high": "🟠", "critical": "🔴"}
TYPE_EMOJI = {"fact": "📖", "preference": "❤️", "task": "✅", "event": "📅",
              "person": "👤", "note": "📝", "insight": "💡"}

if tab_choice == "📝 记录记忆":
    st.title("📝 记录新记忆")
    st.caption("将重要信息存入个人记忆库，AI 将自动打标签")

    with st.form("remember_form"):
        content = st.text_area("记忆内容", placeholder="今天的会议决定了…", height=120)
        col1, col2 = st.columns(2)
        with col1:
            memory_type = st.selectbox("记忆类型", MEMORY_TYPES,
                                        format_func=lambda x: f"{TYPE_EMOJI.get(x, '📝')} {x}")
        with col2:
            importance = st.selectbox("重要程度", IMPORTANCE_LEVELS,
                                       format_func=lambda x: f"{IMPORTANCE_EMOJI.get(x, '⚪')} {x}",
                                       index=1)
        tags_str = st.text_input("自定义标签（逗号分隔）", placeholder="工作,项目A")
        submitted = st.form_submit_button("💾 存入记忆", type="primary")

        if submitted:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            result = run_remember(content, memory_type, importance, tags)
            if result["success"]:
                st.success(f"✅ 已记录 | ID: `{result['id']}` | 自动标签: {result['memory'].tags}")
            else:
                st.error(result.get("error"))

elif tab_choice == "🔍 召回记忆":
    st.title("🔍 召回相关记忆")
    st.caption("通过关键词搜索匹配相关记忆")

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        query = st.text_input("搜索关键词", placeholder="例如：项目会议")
    with col2:
        filter_type = st.selectbox("类型筛选", ["全部"] + MEMORY_TYPES)
    with col3:
        filter_imp = st.selectbox("重要性", ["全部"] + IMPORTANCE_LEVELS)

    if st.button("🔍 搜索", type="primary"):
        result = run_recall(
            query,
            memory_type=None if filter_type == "全部" else filter_type,
            importance=None if filter_imp == "全部" else filter_imp
        )
        st.write(f"找到 **{result['count']}** 条匹配记忆")
        for entry in result["results"]:
            with st.expander(
                f"{TYPE_EMOJI.get(entry.memory_type, '📝')} {entry.content[:50]}… "
                f"| {IMPORTANCE_EMOJI.get(entry.importance, '⚪')} {entry.importance} "
                f"| {entry.created_at}"
            ):
                st.write(entry.content)
                st.write(f"**标签**: {', '.join(entry.tags) if entry.tags else '无'}")
                st.write(f"**ID**: `{entry.id}` | **访问次数**: {entry.access_count}")
                if st.button("🗑️ 删除", key=f"del_{entry.id}"):
                    run_forget(entry.id)
                    st.rerun()

elif tab_choice == "📚 记忆库":
    st.title("📚 记忆库管理")
    limit = st.slider("显示数量", 10, 100, 30)
    result = run_list_memories(limit)
    st.write(f"共 **{result['count']}** 条记忆（最新 {limit} 条）")

    for entry in result["memories"]:
        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
        col1.write(f"{TYPE_EMOJI.get(entry.memory_type, '📝')} {entry.content[:60]}…")
        col2.write(entry.memory_type)
        col3.write(f"{IMPORTANCE_EMOJI.get(entry.importance)} {entry.importance}")
        col4.write(entry.created_at[:10])

elif tab_choice == "📊 统计":
    st.title("📊 记忆库统计")
    stats = run_get_stats()
    st.metric("记忆总数", stats["total"])
    st.write("**按类型分布**")
    for t, cnt in stats["by_type"].items():
        if cnt > 0:
            st.progress(cnt / max(stats["total"], 1), text=f"{TYPE_EMOJI.get(t, '📝')} {t}: {cnt}")
    st.write("**按重要性分布**")
    for imp, cnt in stats["by_importance"].items():
        if cnt > 0:
            st.progress(cnt / max(stats["total"], 1), text=f"{IMPORTANCE_EMOJI.get(imp)} {imp}: {cnt}")

elif tab_choice == "💬 AI 助手":
    st.title("💬 记忆 AI 助手")
    st.caption("告诉 AI 你想记住什么，它会帮你整理")
    if "messages_29" not in st.session_state:
        st.session_state.messages_29 = []
    for msg in st.session_state.messages_29:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("跟 AI 对话，告诉它你想记住什么…"):
        st.session_state.messages_29.append({"role": "user", "content": prompt})
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
        st.session_state.messages_29.append({"role": "assistant", "content": full})
