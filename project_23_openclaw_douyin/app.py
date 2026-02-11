# app.py — Streamlit UI for openclaw 抖音脚本 Agent
import streamlit as st

st.set_page_config(
    page_title="openclaw 抖音 Agent",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, PLATFORM, DAILY_POST_LIMIT, VIDEO_DURATIONS
from agent import run_generate_script, run_optimize_tags, run_plan_schedule, run_get_best_time, stream_chat

if "messages" not in st.session_state:
    st.session_state.messages = []
if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = []

with st.sidebar:
    st.markdown("## 🎵 openclaw 抖音 Agent")
    st.caption("抖音视频脚本生成 · 标签优化 · 排期规划")
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

st.markdown("# 🎵 openclaw — 抖音 Agent")
st.caption(f"Powered by **{DEFAULT_MODEL}** | 平台: {PLATFORM}")

tab1, tab2, tab3 = st.tabs(["🎬 脚本生成", "🏷️ 标签优化", "📅 发布排期"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("视频话题", placeholder="例如: 程序员的日常、健身干货")
        keywords_raw = st.text_input("关键词（逗号分隔）", placeholder="例如: 高效学习, 早起, 专注")
    with col2:
        duration = st.selectbox("视频时长（秒）", VIDEO_DURATIONS, index=2)
        style = st.selectbox("内容风格",
                              ["educational", "entertaining", "motivational"],
                              format_func=lambda x: {"educational": "知识干货", "entertaining": "搞笑娱乐", "motivational": "励志正能量"}[x])

    if st.button("🚀 生成脚本", type="primary"):
        if not topic:
            st.warning("请输入话题")
        else:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None
            with st.spinner("生成视频脚本中..."):
                result = run_generate_script(topic, keywords, duration, style)
            st.success("✅ 脚本生成完成")

            with st.expander("🎬 视频脚本", expanded=True):
                st.markdown(f"**标题:** {result['视频标题']}")
                st.caption(f"时长: {result['时长(秒)']}s | 脚本字数: {result['脚本字数']}")
                st.divider()

                st.markdown("**🪝 开场钩子（前3秒）**")
                st.info(result["开场钩子"])

                st.markdown("**📝 主体内容**")
                st.markdown(result["主体内容"])

                st.markdown("**📣 结尾引导（CTA）**")
                st.success(result["结尾引导"])

                st.divider()
                col_a, col_b = st.columns(2)
                col_a.markdown("**标签:** " + "  ".join(f"`{t}`" for t in result["话题标签"]))
                col_b.metric("合规", "✅ 通过" if result["合规检查"]["passed"] else "❌ 违规")

            st.session_state.generated_posts.append(result["视频标题"])

with tab2:
    topic_tag = st.text_input("话题", placeholder="例如: 知识分享", key="topic_tag")
    kw_tag = st.text_input("关键词", placeholder="例如: 干货, 技巧", key="kw_tag")
    if st.button("🔍 优化标签", type="primary"):
        if topic_tag:
            kws = [k.strip() for k in kw_tag.split(",") if k.strip()] if kw_tag else None
            result = run_optimize_tags(topic_tag, kws)
            st.metric("预估互动得分", result["预估互动得分"])
            st.markdown("**推荐标签:** " + "  ".join(f"`#{t}`" for t in result["推荐标签"]))
            st.markdown("**热门标签:** " + "  ".join(f"`#{t}`" for t in result["热门标签"]))

with tab3:
    if st.session_state.generated_posts:
        st.info(f"已有 {len(st.session_state.generated_posts)} 条视频待发布")
        if st.button("📅 生成发布计划", type="primary"):
            result = run_plan_schedule(st.session_state.generated_posts)
            st.metric("下次发布", result["下一次发布"])
            st.dataframe(result["发布时间表"], use_container_width=True)
    else:
        st.info("请先生成视频脚本")

    st.divider()
    st.markdown("#### 💬 AI 运营顾问")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("问我关于抖音运营的问题..."):
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
