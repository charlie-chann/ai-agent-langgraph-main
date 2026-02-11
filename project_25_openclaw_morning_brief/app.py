"""Project 25 - 早报生成 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import run_generate_brief, run_list_sources, run_add_source, stream_chat
from config import DEFAULT_RSS_SOURCES, TOP_STORIES_COUNT

st.set_page_config(
    page_title="📰 早报生成 Agent",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar
with st.sidebar:
    st.markdown("# 📰 早报生成 Agent")
    st.caption("OpenClaw 内容管道 · Project 25")
    st.divider()
    st.markdown("**功能模块**")
    tab_choice = st.radio(
        "选择功能",
        ["📋 生成今日早报", "📡 RSS 源管理", "💬 AI 对话"],
        label_visibility="collapsed"
    )
    st.divider()
    output_format = st.selectbox("输出格式", ["markdown", "plain"])
    top_n = st.slider("精选头条数量", 3, 15, TOP_STORIES_COUNT)
    st.divider()
    st.caption("OpenClaw · 基于 Ollama qwen3.5")

# ─── 生成早报 Tab ─────────────────────────────────────────────────────────
if tab_choice == "📋 生成今日早报":
    st.title("📰 今日早报生成")
    st.caption("自动聚合多源 RSS，生成结构化每日早报")

    col1, col2 = st.columns([2, 1])
    with col1:
        custom_date = st.text_input("自定义日期（留空=今天）", placeholder="2024年01月01日")
    with col2:
        generate_btn = st.button("🚀 立即生成早报", type="primary", use_container_width=True)

    if generate_btn:
        with st.spinner("正在聚合多源资讯，生成早报…"):
            result = run_generate_brief(
                date=custom_date if custom_date else None,
                output_format=output_format
            )

        if result["success"]:
            brief = result["brief"]
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("📰 资讯总数", result["article_count"])
            col_b.metric("📋 精选头条", len(brief.top_stories))
            col_c.metric("📝 内容长度", f"{result['brief'].word_count} 字")

            st.divider()
            st.markdown(result["content"])

            st.download_button(
                label="⬇️ 下载早报",
                data=result["content"],
                file_name=f"morning_brief_{brief.date.replace('年', '').replace('月', '').replace('日', '')}.md",
                mime="text/markdown"
            )
        else:
            st.error(f"生成失败：{result.get('error', '未知错误')}")

# ─── RSS 源管理 Tab ────────────────────────────────────────────────────────
elif tab_choice == "📡 RSS 源管理":
    st.title("📡 RSS 订阅源管理")

    sources = run_list_sources()
    st.subheader(f"当前已配置 {len(sources)} 个来源")
    for i, s in enumerate(sources):
        with st.expander(f"📌 {s['name']} — {s['url'][:50]}…"):
            st.json(s)

    st.divider()
    st.subheader("➕ 添加新 RSS 源")
    with st.form("add_source_form"):
        name = st.text_input("来源名称", placeholder="BBC新闻")
        url = st.text_input("RSS URL", placeholder="https://...")
        tags_str = st.text_input("标签（逗号分隔）", placeholder="国际,新闻")
        category = st.selectbox("分类", ["国际要闻", "科技动态", "财经市场", "国内新闻", "其他"])
        submitted = st.form_submit_button("添加来源")
        if submitted:
            tags = [t.strip() for t in tags_str.split(",") if t.strip()]
            result = run_add_source(name, url, tags, category)
            if result["success"]:
                st.success(f"添加成功！共 {result['source_count']} 个来源")
            else:
                st.error(result.get("error", "添加失败"))

# ─── AI 对话 Tab ──────────────────────────────────────────────────────────
elif tab_choice == "💬 AI 对话":
    st.title("💬 早报 AI 助手")
    st.caption("向 AI 提问关于今日早报的任何问题")

    if "messages_25" not in st.session_state:
        st.session_state.messages_25 = []

    for msg in st.session_state.messages_25:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("问问关于今日新闻的任何问题…"):
        st.session_state.messages_25.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            container = st.empty()
            full_response = ""
            try:
                for chunk in stream_chat(prompt):
                    full_response += chunk
                    container.markdown(full_response + "▌")
                container.markdown(full_response)
            except Exception as e:
                container.error(f"连接 Ollama 失败：{e}")
                full_response = f"Error: {e}"

        st.session_state.messages_25.append({"role": "assistant", "content": full_response})
