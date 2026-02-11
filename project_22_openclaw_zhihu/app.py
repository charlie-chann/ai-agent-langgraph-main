# app.py — Streamlit UI for openclaw 知乎内容 Agent
import streamlit as st

st.set_page_config(
    page_title="openclaw 知乎 Agent",
    page_icon="🔵",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, PLATFORM, DAILY_POST_LIMIT
from agent import run_generate_answer, run_optimize_tags, run_plan_schedule, run_get_best_time, stream_chat

if "messages" not in st.session_state:
    st.session_state.messages = []
if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = []

with st.sidebar:
    st.markdown("## 🔵 openclaw 知乎 Agent")
    st.caption("知乎高质量回答生成 · 标签优化 · 发布排期")
    st.divider()
    st.text_input("Ollama Model", value=DEFAULT_MODEL, disabled=True)
    st.divider()
    st.metric("每日发布上限", DAILY_POST_LIMIT)
    best_time = run_get_best_time()
    st.markdown("**最佳发布时间**")
    for k, v in best_time.items():
        st.caption(f"{k}: {v}")
    st.divider()
    if st.button("🗑️ 清空记录"):
        st.session_state.messages = []
        st.session_state.generated_posts = []
        st.rerun()

st.markdown("# 🔵 openclaw — 知乎 Agent")
st.caption(f"Powered by **{DEFAULT_MODEL}** | 平台: {PLATFORM}")

tab1, tab2, tab3 = st.tabs(["✍️ 回答生成", "🏷️ 标签优化", "📅 发布排期"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        question = st.text_input("问题标题", placeholder="例如: 如何提升编程能力？")
        topic = st.text_input("所属领域", placeholder="例如: 科技、职场、教育")
    with col2:
        expertise = st.selectbox("专业度",
                                  ["beginner", "intermediate", "expert"],
                                  index=1,
                                  format_func=lambda x: {"beginner": "入门分享", "intermediate": "专业分析", "expert": "深度洞见"}[x])

    if st.button("🚀 生成回答", type="primary"):
        if not question:
            st.warning("请输入问题")
        else:
            with st.spinner("生成回答中..."):
                result = run_generate_answer(question, topic or "科技", expertise)
            st.success("✅ 回答生成完成")
            with st.expander("📄 知乎回答", expanded=True):
                st.markdown(f"**问题:** {result['标题/问题']}")
                st.divider()
                st.markdown(result["正文"])
                st.divider()
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("字数", result["字数"])
                col_b.metric("预估点赞", result["预估点赞"])
                col_c.metric("合规", "✅" if result["合规检查"]["passed"] else "❌")
                st.markdown("**标签:** " + "  ".join(f"`{t}`" for t in result["标签"]))
            st.session_state.generated_posts.append(question[:50])

with tab2:
    topic_tag = st.text_input("领域话题", placeholder="例如: 职场发展", key="topic_tag")
    kw_tag = st.text_input("关键词", placeholder="例如: 晋升, 跳槽", key="kw_tag")
    if st.button("🔍 优化标签", type="primary"):
        if topic_tag:
            kws = [k.strip() for k in kw_tag.split(",") if k.strip()] if kw_tag else None
            result = run_optimize_tags(topic_tag, kws)
            st.metric("预估互动得分", result["预估互动得分"])
            st.markdown("**推荐标签:** " + "  ".join(f"`{t}`" for t in result["推荐标签"]))

with tab3:
    if st.session_state.generated_posts:
        st.info(f"已有 {len(st.session_state.generated_posts)} 条待发布内容")
        if st.button("📅 生成发布计划", type="primary"):
            result = run_plan_schedule(st.session_state.generated_posts)
            st.metric("下次发布", result["下一次发布"])
            st.dataframe(result["发布时间表"], use_container_width=True)
    else:
        st.info("请先生成回答内容")

    st.divider()
    st.markdown("#### 💬 AI 写作助手")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("问我关于知乎写作和运营的问题..."):
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
