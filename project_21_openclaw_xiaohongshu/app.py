# app.py — openclaw 小红书内容 Agent Streamlit UI
#
# 【职责】提供三个功能 Tab + AI 运营顾问对话：
#   Tab1 笔记生成  → run_generate_post()
#   Tab2 标签优化  → run_optimize_tags()
#   Tab3 发布排期  → run_plan_schedule() + stream_chat() 对话
import streamlit as st

st.set_page_config(
    page_title="openclaw 小红书 Agent",
    page_icon="📕",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, PLATFORM, DAILY_POST_LIMIT
from agent import run_generate_post, run_optimize_tags, run_plan_schedule, run_get_best_time, stream_chat

if "messages" not in st.session_state:
    st.session_state.messages = []          # AI 运营顾问对话历史
if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = [] # 已生成笔记预览，供排期 Tab 使用

# ── 侧边栏：平台参数 + 最佳发布时间 ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📕 openclaw 小红书 Agent")
    st.caption("小红书图文笔记生成 · 标签优化 · 发布排期")
    st.divider()
    st.markdown("### ⚙️ 模型配置")
    st.text_input("Ollama Model", value=DEFAULT_MODEL, disabled=True)
    st.divider()
    st.markdown("### 📊 平台参数")
    st.metric("每日发布上限", DAILY_POST_LIMIT)
    best_time = run_get_best_time()  # 调用 schedule_tool 获取最佳时段
    st.markdown("**最佳发布时间**")
    for k, v in best_time.items():
        st.caption(f"{k}: {v}")
    st.divider()
    if st.button("🗑️ 清空记录"):
        st.session_state.messages = []
        st.session_state.generated_posts = []
        st.rerun()

st.markdown("# 📕 openclaw — 小红书 Agent")
st.caption(f"Powered by **{DEFAULT_MODEL}** | 平台: {PLATFORM}")

tab1, tab2, tab3 = st.tabs(["✍️ 笔记生成", "🏷️ 标签优化", "📅 发布排期"])

# ── Tab1：生成小红书笔记 ─────────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("领域/话题", placeholder="例如: 护肤、穿搭、美食", key="topic_gen")
        keywords_raw = st.text_input("关键词（逗号分隔）", placeholder="例如: 精华液, 补水, 敏感肌")
    with col2:
        style = st.selectbox("笔记风格", ["lifestyle", "tutorial", "review"],
                             format_func=lambda x: {"lifestyle": "生活方式", "tutorial": "教程攻略", "review": "测评分享"}[x])

    if st.button("🚀 生成笔记", type="primary"):
        if not topic:
            st.warning("请输入话题")
        else:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None
            with st.spinner("生成笔记中..."):
                result = run_generate_post(topic, keywords, style)  # 调用 content_generator 工具
            st.success("✅ 笔记生成完成")
            with st.expander("📄 笔记内容", expanded=True):
                st.markdown(f"### {result['标题']}")
                st.markdown(result["正文"])
                st.divider()
                col_a, col_b = st.columns(2)
                col_a.metric("字数", result["字数"])
                col_b.metric("合规", "✅ 通过" if result["合规检查"]["passed"] else "❌ 违规")
                st.markdown("**标签:** " + "  ".join(f"`{t}`" for t in result["标签"]))
                st.markdown("**配图建议:** " + " · ".join(result.get("配图建议", [])))
            st.session_state.generated_posts.append(result["正文"][:50])  # 保存预览供排期使用

# ── Tab2：优化话题标签 ───────────────────────────────────────────────────────
with tab2:
    topic_tag = st.text_input("话题", placeholder="例如: 护肤、穿搭", key="topic_tag")
    kw_tag = st.text_input("关键词", placeholder="例如: 精华, 防晒", key="kw_tag")
    if st.button("🔍 优化标签", type="primary"):
        if topic_tag:
            kws = [k.strip() for k in kw_tag.split(",") if k.strip()] if kw_tag else None
            result = run_optimize_tags(topic_tag, kws)  # 调用 tag_optimizer 工具
            st.metric("预估互动得分", result["预估互动得分"])
            st.markdown("**推荐标签:** " + "  ".join(f"`#{t}`" for t in result["推荐标签"]))
            st.markdown("**热门标签:** " + "  ".join(f"`#{t}`" for t in result["热门标签"]))

# ── Tab3：发布排期 + AI 运营顾问对话 ─────────────────────────────────────────
with tab3:
    if st.session_state.generated_posts:
        st.info(f"已有 {len(st.session_state.generated_posts)} 条待发布内容")
        if st.button("📅 生成发布计划", type="primary"):
            result = run_plan_schedule(st.session_state.generated_posts)  # 调用 schedule_tool
            st.metric("下次发布", result["下一次发布"])
            st.dataframe(result["发布时间表"], use_container_width=True)
    else:
        st.info("请先生成笔记内容")

    st.divider()
    st.markdown("#### 💬 AI 运营顾问")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("问我关于小红书运营的任何问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            container = st.empty()
            full = ""
            # stream_chat → llm.stream 逐 token 显示打字机效果
            for chunk in stream_chat(prompt):
                full += chunk
                container.markdown(full + "▌")
            container.markdown(full)
        st.session_state.messages.append({"role": "assistant", "content": full})
