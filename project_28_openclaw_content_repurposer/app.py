"""Project 28 - 内容二次加工 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import run_repurpose, run_repurpose_single, run_compliance_check, run_get_platform_specs, stream_chat
from config import PLATFORM_SPECS, DEFAULT_TARGET_PLATFORMS

st.set_page_config(
    page_title="♻️ 内容二次加工 Agent",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# ♻️ 内容二次加工")
    st.caption("OpenClaw 内容管道 · Project 28")
    st.divider()
    tab_choice = st.radio(
        "功能",
        ["🔄 一键多平台适配", "📐 单平台改写", "✅ 合规检查", "💬 AI 顾问"],
        label_visibility="collapsed"
    )
    st.divider()
    selected_platforms = st.multiselect(
        "目标平台", DEFAULT_TARGET_PLATFORMS, default=DEFAULT_TARGET_PLATFORMS
    )
    st.divider()
    st.caption("OpenClaw · Ollama qwen3.5")

PLATFORM_EMOJI = {
    "weibo": "🌊", "xiaohongshu": "🌸", "zhihu": "🔍",
    "douyin": "🎵", "twitter": "🐦"
}

if tab_choice == "🔄 一键多平台适配":
    st.title("♻️ 一键多平台内容适配")
    st.caption("输入原始内容，自动改写为各平台最佳格式")

    topic = st.text_input("内容主题", placeholder="例如：人工智能改变教育")
    content = st.text_area("原始内容", height=180,
                            placeholder="粘贴你的长文、新闻摘要或核心观点…")

    if st.button("🚀 开始适配", type="primary"):
        if not content or not topic:
            st.warning("请填写主题和内容")
        else:
            with st.spinner("正在为各平台智能改写…"):
                result = run_repurpose(content, topic, selected_platforms)

            if result["success"]:
                st.success(f"已适配 {len(result['platforms_adapted'])} 个平台")

                for platform, adapted in result["results"].items():
                    emoji = PLATFORM_EMOJI.get(platform, "📱")
                    spec = PLATFORM_SPECS.get(platform, {})
                    compliant = result["compliance_summary"].get(platform, True)
                    badge = "✅" if compliant else "⚠️ 超限"

                    with st.expander(f"{emoji} {platform.capitalize()} — {adapted.char_count}字 {badge}"):
                        st.write(f"**标题**: {adapted.title}")
                        st.text_area("正文", adapted.body, height=120, key=f"body_{platform}")
                        if adapted.hashtags:
                            st.write("**标签**: " + " ".join(adapted.hashtags))
                        st.write(f"字符限制: {spec.get('max_chars', '—')} | 当前: {adapted.char_count}")
            else:
                st.error(result.get("error"))

elif tab_choice == "📐 单平台改写":
    st.title("📐 指定平台内容改写")
    platform = st.selectbox("目标平台", list(PLATFORM_SPECS.keys()))
    topic = st.text_input("主题")
    content = st.text_area("原始内容", height=150)

    if st.button("改写", type="primary"):
        if content and topic:
            with st.spinner("改写中…"):
                result = run_repurpose_single(content, topic, platform)
            if result["success"]:
                adapted = result["result"]
                st.subheader(f"✅ {platform.capitalize()} 版本")
                st.write(f"**标题**: {adapted.title}")
                st.text_area("正文", adapted.body, height=150)
                st.write(f"字符数: {adapted.char_count} | 合规: {'✅' if result['compliant'] else '⚠️'}")
            else:
                st.error(result["error"])

elif tab_choice == "✅ 合规检查":
    st.title("✅ 平台合规检查")
    platform = st.selectbox("平台", list(PLATFORM_SPECS.keys()))
    content = st.text_area("待检查内容", height=120)
    if st.button("检查"):
        result = run_compliance_check(content, platform)
        if result.get("compliant"):
            st.success(f"✅ 合规 | 字符数: {result['char_count']} / {result['max_chars']}")
        else:
            st.error(f"⚠️ 超限 {result.get('chars_over', 0)} 字符 | {result['char_count']} / {result['max_chars']}")

elif tab_choice == "💬 AI 顾问":
    st.title("💬 内容改写顾问")
    if "messages_28" not in st.session_state:
        st.session_state.messages_28 = []
    for msg in st.session_state.messages_28:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    if prompt := st.chat_input("问关于内容适配的问题…"):
        st.session_state.messages_28.append({"role": "user", "content": prompt})
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
        st.session_state.messages_28.append({"role": "assistant", "content": full})
