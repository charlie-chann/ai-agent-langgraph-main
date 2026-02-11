"""Project 26 - 深度调研 Agent Streamlit UI"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from agent import run_research, run_validate_topic, run_save_report, stream_chat
from config import RESEARCH_DEPTHS, DEFAULT_DEPTH

st.set_page_config(
    page_title="🔬 深度调研 Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

with st.sidebar:
    st.markdown("# 🔬 深度调研 Agent")
    st.caption("OpenClaw 内容管道 · Project 26")
    st.divider()
    tab_choice = st.radio(
        "功能选择",
        ["🔍 执行调研", "✅ 话题验证", "💬 AI 分析师"],
        label_visibility="collapsed"
    )
    st.divider()
    depth = st.selectbox("调研深度", RESEARCH_DEPTHS, index=RESEARCH_DEPTHS.index(DEFAULT_DEPTH))
    st.divider()
    st.caption("OpenClaw · 基于 Ollama qwen3.5")

if tab_choice == "🔍 执行调研":
    st.title("🔬 深度调研报告生成")
    st.caption("输入话题，Agent 将从多个角度系统性调研，生成可信度评估报告")

    topic = st.text_area("调研话题", placeholder="例如：量子计算对密码学的影响", height=80)
    run_btn = st.button("🚀 开始调研", type="primary")

    if run_btn and topic:
        with st.spinner(f"正在进行{depth}级别调研，请稍候…"):
            result = run_research(topic.strip(), depth=depth)

        if result["success"]:
            report = result["report"]
            col1, col2, col3 = st.columns(3)
            col1.metric("📚 信息来源数", result["total_sources"])
            col2.metric("🎯 平均可信度", f"{result['avg_credibility']:.0%}")
            col3.metric("📄 报告长度", f"{report.word_count} 字")

            st.divider()
            st.markdown(result["content"])

            col_save, col_dl = st.columns(2)
            with col_dl:
                st.download_button("⬇️ 下载报告", result["content"],
                                   f"research_{topic[:20]}.md", "text/markdown")
            with col_save:
                if st.button("💾 保存到本地"):
                    save_result = run_save_report(report)
                    if save_result["success"]:
                        st.success(f"已保存至 {save_result['path']}")
        else:
            st.error(f"调研失败：{result.get('error')}")

elif tab_choice == "✅ 话题验证":
    st.title("✅ 话题可研性验证")
    st.caption("快速评估某话题是否有足够的数据支持深度调研")

    topic = st.text_input("输入话题", placeholder="AI大语言模型")
    validate_btn = st.button("🔍 验证")

    if validate_btn and topic:
        with st.spinner("快速搜索中…"):
            result = run_validate_topic(topic.strip())

        badge = "✅ 可调研" if result["researchable"] else "⚠️ 数据不足"
        st.metric("评估结果", badge)
        col1, col2 = st.columns(2)
        col1.metric("发现来源数", result["source_count"])
        col2.metric("平均可信度", f"{result['avg_credibility']:.0%}")

        if not result["researchable"]:
            st.warning("当前话题数据来源较少，建议换用更通用的关键词后重试。")

elif tab_choice == "💬 AI 分析师":
    st.title("💬 AI 调研分析师")

    if "messages_26" not in st.session_state:
        st.session_state.messages_26 = []

    for msg in st.session_state.messages_26:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("问调研相关问题…"):
        st.session_state.messages_26.append({"role": "user", "content": prompt})
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
                container.error(f"连接 Ollama 失败：{e}")
                full = str(e)
        st.session_state.messages_26.append({"role": "assistant", "content": full})
