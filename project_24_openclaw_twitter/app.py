# app.py — Streamlit UI for openclaw Twitter/X Agent
import streamlit as st

st.set_page_config(
    page_title="openclaw Twitter Agent",
    page_icon="🐦",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, PLATFORM, DAILY_POST_LIMIT, MAX_TWEET_LENGTH, MAX_THREAD_TWEETS
from agent import run_generate_tweet, run_generate_thread, run_optimize_tags, run_plan_schedule, run_get_best_time, stream_chat

if "messages" not in st.session_state:
    st.session_state.messages = []
if "generated_posts" not in st.session_state:
    st.session_state.generated_posts = []

with st.sidebar:
    st.markdown("## 🐦 openclaw Twitter Agent")
    st.caption("Tweet & Thread Generation · Tag Optimizer · Schedule")
    st.divider()
    st.text_input("Ollama Model", value=DEFAULT_MODEL, disabled=True)
    st.divider()
    st.metric("Daily post limit", DAILY_POST_LIMIT)
    st.metric("Max tweet length", MAX_TWEET_LENGTH)
    best_time = run_get_best_time()
    st.markdown("**Best posting times**")
    for k, v in best_time.items():
        st.caption(f"{k}: {v}")
    st.divider()
    if st.button("🗑️ Clear history"):
        st.session_state.messages = []
        st.session_state.generated_posts = []
        st.rerun()

st.markdown("# 🐦 openclaw — Twitter/X Agent")
st.caption(f"Powered by **{DEFAULT_MODEL}** | Platform: {PLATFORM}")

tab1, tab2, tab3, tab4 = st.tabs(["✍️ Single Tweet", "🧵 Thread", "🏷️ Hashtags", "📅 Schedule"])

with tab1:
    col1, col2 = st.columns([2, 1])
    with col1:
        topic = st.text_input("Topic", placeholder="e.g. AI tools, Python tips", key="topic_tweet")
        keywords_raw = st.text_input("Keywords (comma-separated)", placeholder="e.g. LLM, productivity")
    with col2:
        style = st.selectbox("Style",
                              ["informative", "engaging", "promotional", "thread_hook"],
                              format_func=lambda x: {"informative": "Info/Tips", "engaging": "Conversation", "promotional": "Promo", "thread_hook": "Thread Hook"}[x])

    if st.button("🚀 Generate Tweet", type="primary", key="gen_tweet"):
        if not topic:
            st.warning("Please enter a topic")
        else:
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else None
            with st.spinner("Generating tweet..."):
                result = run_generate_tweet(topic, keywords, style)
            st.success("✅ Done!")
            with st.expander("📄 Tweet Content", expanded=True):
                st.markdown(f"> {result['内容']}")
                col_a, col_b = st.columns(2)
                col_a.metric("Characters", f"{result['字符数']}/{MAX_TWEET_LENGTH}")
                col_b.metric("Compliant", "✅" if result["合规检查"]["passed"] else "❌")
                st.markdown("**Hashtags:** " + "  ".join(f"`#{t}`" for t in result["标签"]))
            st.session_state.generated_posts.append(result["内容"][:50])

with tab2:
    topic_th = st.text_input("Thread Topic", placeholder="e.g. Machine Learning basics", key="topic_thread")
    num_tweets = st.slider("Number of tweets", 3, MAX_THREAD_TWEETS, 5)
    points_raw = st.text_area("Key points (one per line, optional)", placeholder="Point 1\nPoint 2\nPoint 3", height=100)

    if st.button("🧵 Generate Thread", type="primary"):
        if not topic_th:
            st.warning("Please enter a topic")
        else:
            points = [p.strip() for p in points_raw.splitlines() if p.strip()] if points_raw else None
            with st.spinner(f"Generating {num_tweets}-tweet thread..."):
                result = run_generate_thread(topic_th, points, num_tweets)
            st.success(f"✅ Thread: {result['总条数']} tweets")
            for i, tweet in enumerate(result["推文列表"], 1):
                with st.expander(f"Tweet {i}", expanded=i == 1):
                    st.markdown(f"> {tweet}")
                    st.caption(f"Length: {len(tweet)}/{MAX_TWEET_LENGTH}")
            st.markdown("**Hashtags:** " + "  ".join(f"`#{t}`" for t in result["标签"]))
            st.session_state.generated_posts.extend([t[:50] for t in result["推文列表"]])

with tab3:
    topic_tag = st.text_input("Topic", placeholder="e.g. AI, Python", key="topic_tag")
    kw_tag = st.text_input("Keywords", placeholder="e.g. LLM, developer", key="kw_tag")
    if st.button("🔍 Optimize Hashtags", type="primary"):
        if topic_tag:
            kws = [k.strip() for k in kw_tag.split(",") if k.strip()] if kw_tag else None
            result = run_optimize_tags(topic_tag, kws)
            st.metric("Engagement score", result["预估互动得分"])
            st.info("💡 Twitter recommends max 3 hashtags per tweet")
            st.markdown("**Recommended:** " + "  ".join(f"`#{t}`" for t in result["推荐标签"]))
            st.markdown("**Trending:** " + "  ".join(f"`#{t}`" for t in result["热门标签"]))

with tab4:
    if st.session_state.generated_posts:
        st.info(f"{len(st.session_state.generated_posts)} tweets ready to schedule")
        if st.button("📅 Generate Schedule (UTC)", type="primary"):
            result = run_plan_schedule(st.session_state.generated_posts)
            st.metric("Next post", result["下一次发布"])
            st.dataframe(result["发布时间表"], use_container_width=True)
    else:
        st.info("Generate some tweets first")

    st.divider()
    st.markdown("#### 💬 AI Strategy Assistant")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("Ask me about Twitter growth strategy..."):
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
