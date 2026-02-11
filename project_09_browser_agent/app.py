# app.py — Browser Automation Agent Streamlit UI
import sys
import time
from pathlib import Path

import streamlit as st

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🌐 Browser Agent",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌐 Browser Agent")
    st.markdown("*浏览器自动化智能体*")
    st.divider()

    st.markdown("### 模型配置")
    from config import DEFAULT_MODEL, OLLAMA_BASE_URL
    model_name = st.text_input("模型", value=DEFAULT_MODEL)
    ollama_url = st.text_input("Ollama URL", value=OLLAMA_BASE_URL)
    max_steps = st.slider("最大执行步数", 3, 20, 10)

    st.divider()
    st.markdown("### 关于本项目")
    st.markdown("""
**功能特性：**
- 🔍 网页内容抓取与分析
- 🔗 链接提取与跟踪
- 📝 自动生成结构化报告
- 🛡️ URL 安全验证

**工具列表：**
- `navigate_to` — 导航网页
- `get_page_text` — 获取页面文本
- `extract_links` — 提取链接
- `search_in_page` — 页面内搜索
- `web_search_and_open` — 搜索并打开
    """)

    st.divider()
    st.markdown("### 示例任务")
    examples = [
        "搜索 Python LangChain 最新教程",
        "访问 https://httpbin.org/json 并提取内容",
        "提取 https://example.com 的所有链接",
    ]
    for ex in examples:
        if st.button(ex, key=f"ex_{ex[:20]}"):
            st.session_state["task_input"] = ex

# ── Main ──────────────────────────────────────────────────────────────────────
st.title("🌐 Browser Automation Agent")
st.caption("基于 LangGraph ReAct 的网页自动化智能体，支持搜索、抓取、提取和报告生成")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "task_input" not in st.session_state:
    st.session_state.task_input = ""

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "steps" in msg:
            with st.expander(f"🔧 执行步骤 ({len(msg['steps'])} 步)", expanded=False):
                for i, step in enumerate(msg["steps"]):
                    st.markdown(f"**Step {step.get('step', i+1)}** ({step.get('time_ms', 0)}ms)")
                    st.code(step.get("preview", ""), language="text")
            if "pages" in msg and msg["pages"]:
                with st.expander("📄 访问的页面"):
                    for url in set(msg["pages"]):
                        st.markdown(f"- {url}")
        st.markdown(msg["content"])

# Task input
task = st.chat_input("输入浏览器自动化任务（如：搜索Python教程并总结）") or st.session_state.get("task_input", "")
if task and task != st.session_state.get("_last_task", ""):
    st.session_state["_last_task"] = task
    st.session_state["task_input"] = ""

    # Show user message
    with st.chat_message("user"):
        st.markdown(task)
    st.session_state.chat_history.append({"role": "user", "content": task})

    # Run agent
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        steps_placeholder = st.empty()
        report_placeholder = st.empty()

        try:
            # Update config with sidebar values
            import config
            config.DEFAULT_MODEL = model_name
            config.OLLAMA_BASE_URL = ollama_url
            config.BROWSER_MAX_STEPS = max_steps

            from agent import stream_browser_task, run_browser_task
            from tools.task_parser import sanitize_instruction

            instruction = sanitize_instruction(task)
            status_placeholder.info("🚀 Agent 启动中...")

            step_logs = []
            pages_visited = []
            final_report = ""

            t0 = time.time()
            for event in stream_browser_task(instruction):
                for node_name, node_state in event.items():
                    if node_name == "plan_and_act":
                        step_count = node_state.get("step_count", 0)
                        status_placeholder.info(f"🤔 思考中... (Step {step_count}/{max_steps})")
                        if node_state.get("step_log"):
                            step_logs = node_state["step_log"]
                    elif node_name == "tools":
                        status_placeholder.info(f"🔧 执行工具调用...")
                        if node_state.get("pages_visited"):
                            pages_visited = node_state["pages_visited"]
                    elif node_name == "synthesize":
                        status_placeholder.info("✍️ 生成报告...")
                        final_report = node_state.get("final_report", "")
                        if node_state.get("step_log"):
                            step_logs = node_state["step_log"]

            elapsed = round(time.time() - t0, 1)
            status_placeholder.success(f"✅ 任务完成 ({elapsed}s)")

            # Show execution steps
            if step_logs:
                with steps_placeholder.expander(f"🔧 执行步骤 ({len(step_logs)} 步)", expanded=False):
                    for step in step_logs:
                        st.markdown(f"**{step.get('step', '?')}** ({step.get('time_ms', 0)}ms)")
                        st.code(step.get("preview", ""), language="text")

            # Show report
            if final_report:
                report_placeholder.markdown(final_report)
            else:
                report_placeholder.warning("⚠️ 未生成报告，请检查任务描述")

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": final_report or "任务执行完成，请查看步骤日志",
                "steps": step_logs,
                "pages": list(set(pages_visited)),
            })

        except ValueError as e:
            status_placeholder.error(f"❌ 输入错误: {e}")
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"❌ {e}",
            })
        except Exception as e:
            status_placeholder.error(f"❌ 执行失败: {e}")
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": f"❌ 执行失败: {e}",
            })
