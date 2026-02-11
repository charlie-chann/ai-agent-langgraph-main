"""
app.py — 企业内网助手 Streamlit Web 界面

【职责】
提供可交互聊天 UI：演示用户切换（RBAC）、快捷问题、会话统计、
工具调用明细展示，并调用 agent.chat 完成推理。

【设计原因】
Streamlit 适合快速搭建企业内部 PoC/demo；侧边栏集中展示角色权限，
帮助培训/验收时理解不同职级的能力差异。
"""
import streamlit as st

st.set_page_config(
    page_title="Enterprise Internal Bot",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL, ROLES
from agent import chat, get_history, clear_history
from tools.rbac import get_user_role, get_allowed_tools

# ── Session 初始化 ────────────────────────────────────────────────────────────
# Streamlit 每次交互 rerun，需用 session_state 持久化用户选择与聊天记录
if "username" not in st.session_state:
    st.session_state.username = "emp_charlie"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "metrics" not in st.session_state:
    st.session_state.metrics = []

# 演示账号与展示标签映射
DEMO_USERS = {
    "emp_charlie":  "👷 Employee",
    "emp_diana":    "👷 Employee",
    "mgr_alice":    "👔 Manager",
    "mgr_bob":      "👔 Manager",
    "admin_user":   "🔑 Admin",
    "guest_visitor":"🔓 Guest",
}

# ── 侧边栏：用户身份、权限、快捷入口 ──────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏢 Enterprise Bot")
    st.caption("IT Support · HR · Tickets · KB · Notifications")
    st.divider()

    st.markdown("### 👤 Login As (Demo)")
    selected_user = st.selectbox(
        "User",
        options=list(DEMO_USERS.keys()),
        format_func=lambda u: f"{DEMO_USERS.get(u, '👤')} {u}",
        index=list(DEMO_USERS.keys()).index(st.session_state.username),
    )
    # 切换用户时清空 UI 聊天记录，避免跨用户上下文混淆
    if selected_user != st.session_state.username:
        st.session_state.username = selected_user
        st.session_state.messages = []
        st.rerun()

    username = st.session_state.username
    role = get_user_role(username)
    allowed = get_allowed_tools(username)

    st.divider()
    st.markdown(f"**Role:** `{role}`")
    st.markdown("**Permissions:**")
    for perm in allowed:
        st.markdown(f"  ✓ `{perm}`")

    st.divider()
    st.markdown("### 💡 Quick Questions")
    examples = [
        "How do I set up VPN?",
        "Submit a PTO request for next Friday",
        "Create IT ticket: laptop won't turn on",
        "What's the expense reimbursement policy?",
        "Send urgent notification to @helpdesk: server down",
        "Show my open tickets",
    ]
    for ex in examples:
        if st.button(ex[:45], key=ex):
            st.session_state["prefill"] = ex

    st.divider()
    st.markdown("### 📊 Session Stats")
    if st.session_state.metrics:
        n = len(st.session_state.metrics)
        avg = sum(m["latency_ms"] for m in st.session_state.metrics) / n
        tool_calls = sum(m["tool_calls"] for m in st.session_state.metrics)
        st.metric("Messages", n)
        st.metric("Avg Latency", f"{avg:.0f}ms")
        st.metric("Tool Calls", tool_calls)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear chat"):
            st.session_state.messages = []
            clear_history(username)  # 同步清除 Agent 侧内存历史
            st.session_state.metrics = []
            st.rerun()

# ── 主区域：聊天展示与输入 ────────────────────────────────────────────────────
st.markdown("# 🏢 Enterprise Internal Assistant")
st.caption(
    f"Logged in as **{username}** ({role})  ·  "
    f"Model: **{DEFAULT_MODEL}** @ {OLLAMA_BASE_URL}"
)

# 渲染已有会话（含 assistant 的工具调用 expander）
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("steps"):
            with st.expander(f"🔧 Tool calls ({len(msg['steps'])})  ·  {msg.get('latency_ms', 0)}ms"):
                for step in msg["steps"]:
                    st.markdown(f"**`{step['tool']}`**  ←  `{str(step['input'])[:100]}`")
                    st.text(str(step["output"])[:300])

# 输入：支持 chat_input 或侧边栏快捷问题 prefill
prefill = st.session_state.pop("prefill", "")
if prompt := st.chat_input("Ask about IT, HR, tickets, policies...", key="chat_input"):
    pass
elif prefill:
    prompt = prefill

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            result = chat(username, prompt)

        st.markdown(result["answer"])

        if result.get("steps"):
            with st.expander(f"🔧 Tool calls ({len(result['steps'])})  ·  {result['latency_ms']}ms"):
                for step in result["steps"]:
                    st.markdown(f"**`{step['tool']}`**  ←  `{str(step['input'])[:100]}`")
                    st.text(str(step["output"])[:300])

    # 持久化本轮消息与性能指标到 session_state
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "steps": result.get("steps", []),
        "latency_ms": result.get("latency_ms", 0),
    })
    st.session_state.metrics.append({
        "latency_ms": result.get("latency_ms", 0),
        "tool_calls": len(result.get("steps", [])),
    })
