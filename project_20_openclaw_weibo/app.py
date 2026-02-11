# app.py — Streamlit UI for openclaw 微博内容 Agent
import streamlit as st

st.set_page_config(
    page_title="openclaw 微博 Agent",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, PLATFORM, DAILY_POST_LIMIT
from agent import run_generate_post, run_generate_batch, run_optimize_tags, run_plan_schedule, stream_chat

# ── Session init ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = []

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🐦 openclaw 微博 Agent")
    st.caption("智能微博内容生成 · 话题优化 · 发布排期")
    st.divider()

    st.markdown("### ⚙️ 模型配置")
    st.text_input("Ollama Model", value=DEFAULT_MODEL, disabled=True)
    st.text_input("Base URL", value=OLLAMA_BASE_URL, disabled=True)
    st.divider()

    st.markdown("### 📊 平台参数")
    st.metric("每日发布上限", DAILY_POST_LIMIT)
    st.metric("平台", PLATFORM.upper())
    st.divider()

    st.markdown("### 💡 使用说明")
    st.markdown("""
    1. 输入话题和关键词
    2. 选择内容风格
    3. 一键生成微博内容
    4. 查看最优标签和发布时间
    """)
    if st.button("🗑️ 清空记录"):
        st.session_state.messages = []
        st.session_state.generated_posts = []
        st.rerun()

# ── Main ─────────────────────────────────────────────────────────────────────
st.markdown("# 🐦 openclaw — 微博内容 Agent")
st.caption(f"Powered by **{DEFAULT_MODEL}** | 平台: {PLATFORM}")

tab1, tab2, tab3 = st.tabs(["✍️ 内容生成", "🏷️ 标签优化", "📅 发布排期"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("话题", placeholder="例如: 人工智能", key="topic_gen")
        keywords_raw = st.text_input("关键词（逗号分隔）", placeholder="例如: ChatGPT, 大模型")
    with col2:
        tone = st.selectbox("内容风格", ["conversational", "informative", "humorous"])
        batch_count = st.slider("批量生成数量", 1, DAILY_POST_LIMIT, 1)

    if st.button("🚀 生成内容", type="primary"):
        if not topic:
            st.warning("请输入话题")
        else:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None

            if batch_count == 1:
                with st.spinner("生成中..."):
                    result = run_generate_post(topic, keywords, tone)
                st.success("✅ 生成完成")
                with st.expander("📄 微博内容", expanded=True):
                    st.markdown(f"**{result['内容']}**")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("字数", result["字数"])
                    col_b.metric("合规", "✅ 通过" if result["合规检查"]["passed"] else "❌ 违规")
                    col_c.metric("情感", result.get("情感标签", "中性"))
                    st.markdown("**标签:**  " + "  ".join(result["话题标签"]))
                st.session_state.generated_posts.append(result["内容"])
            else:
                with st.spinner(f"批量生成 {batch_count} 条..."):
                    results = run_generate_batch(topic, batch_count)
                for i, r in enumerate(results, 1):
                    with st.expander(f"第 {i} 条", expanded=i == 1):
                        st.markdown(r["内容"])
                        st.caption(f"字数: {r['字数']} | 合规: {'✅' if r['合规检查']['passed'] else '❌'}")
                st.session_state.generated_posts.extend([r["内容"] for r in results])

with tab2:
    topic_tag = st.text_input("话题", placeholder="例如: 职场干货", key="topic_tag")
    kw_tag = st.text_input("相关关键词", placeholder="例如: 工作效率, 时间管理", key="kw_tag")
    if st.button("🔍 优化标签", type="primary"):
        if topic_tag:
            kws = [k.strip() for k in kw_tag.split(",") if k.strip()] if kw_tag else None
            with st.spinner("分析中..."):
                result = run_optimize_tags(topic_tag, kws)
            st.success("✅ 标签分析完成")
            col1, col2, col3 = st.columns(3)
            col1.metric("预估互动得分", f"{result['预估互动得分']}")
            with st.expander("推荐标签", expanded=True):
                st.markdown("  ".join(f"`#{t}`" for t in result["推荐标签"]))
            with st.expander("热门标签"):
                st.markdown("  ".join(f"`#{t}`" for t in result["热门标签"]))
            with st.expander("细分标签"):
                st.markdown("  ".join(f"`#{t}`" for t in result.get("细分标签", [])))

with tab3:
    st.markdown("### 📅 智能发布排期")
    if st.session_state.generated_posts:
        st.info(f"已有 {len(st.session_state.generated_posts)} 条待发布内容")
        if st.button("📅 生成发布计划", type="primary"):
            result = run_plan_schedule(st.session_state.generated_posts)
            st.metric("下次发布", result["下一次发布"])
            st.dataframe(result["发布时间表"], use_container_width=True)
    else:
        st.info("请先在「内容生成」标签页生成内容")

    st.divider()
    st.markdown("#### 💬 AI 对话助手")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("问我关于微博运营的任何问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            container = st.empty()
            full = ""
            for chunk in stream_chat(prompt):
                full += chunk
                container.markdown(full + "▌")
            container.markdown(full)
        st.session_state.messages.append({"role": "assistant", "content": full})
