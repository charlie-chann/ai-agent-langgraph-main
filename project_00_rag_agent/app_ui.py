"""
app.py — Streamlit 人机界面（project_00_rag_agent）

【职责】
提供可视化聊天、文档上传、运行时配置与 HITL 审批入口。

【调用方式】
仅通过 httpx 调用 FastAPI 后端（②网关层），不进程内直连 agent / ingest。

【侧边栏能力】
- JWT 登录
- 检索模式、KG 开关、LLM Provider 等环境变量热切换（写入本进程 env，供同机 API 读取时需重启或共享配置）
- 多文件 ingest（admin/editor）
- Admin HITL 批准挂起线程
- 清空会话与指标
"""
from __future__ import annotations

import os

import httpx
import streamlit as st

st.set_page_config(
    page_title="Production RAG Agent",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

for key, default in [
    ("messages", []),
    ("metrics", []),
    ("token", None),
    ("role", "viewer"),
    ("conversation_id", None),
    ("thread_id", None),
    ("ingested", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _api_base() -> str:
    """返回 FastAPI 后端基础 URL（来自环境变量或本地默认值）。"""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


def _login(username: str, password: str) -> bool:
    """调用 /auth/token 登录，成功则写入 session 中的 token 与 role。"""
    try:
        r = httpx.post(f"{_api_base()}/auth/token", json={"username": username, "password": password}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            st.session_state.token = data["access_token"]
            st.session_state.role = data.get("role", "viewer")
            return True
    except Exception as e:
        st.error(f"Login failed: {e}")
    return False


def _auth_headers() -> dict:
    """构造带 Bearer Token 的请求头。"""
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _ensure_conversation() -> str:
    """确保已有会话；若无则创建并回写 conversation_id / thread_id。"""
    if st.session_state.conversation_id:
        return st.session_state.conversation_id
    r = httpx.post(
        f"{_api_base()}/conversations",
        json={},
        headers=_auth_headers(),
        timeout=10,
    )
    r.raise_for_status()
    cid = r.json()["conversation_id"]
    st.session_state.conversation_id = cid
    st.session_state.thread_id = cid
    return cid


def _load_messages_from_api(conversation_id: str) -> None:
    """从服务端拉取会话消息并同步到 Streamlit session_state。"""
    r = httpx.get(
        f"{_api_base()}/conversations/{conversation_id}/messages",
        headers=_auth_headers(),
        timeout=10,
    )
    r.raise_for_status()
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"], "meta": m.get("metadata") or {}}
        for m in r.json().get("messages", [])
        if m["role"] in ("user", "assistant")
    ]


def _chat(message: str) -> dict:
    """向当前会话发送一条消息并返回 API JSON 响应。"""
    cid = _ensure_conversation()
    r = httpx.post(
        f"{_api_base()}/conversations/{cid}/chat",
        json={"message": message},
        headers=_auth_headers(),
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _ingest(files) -> dict:
    """上传文件到 /ingest 接口并返回入库结果。"""
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    multipart = [("files", (f.name, f.getvalue(), f.type or "application/octet-stream")) for f in files]
    r = httpx.post(f"{_api_base()}/ingest", files=multipart, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()


with st.sidebar:
    st.markdown("## 🏭 Production RAG")
    st.caption("Hybrid · KG · HITL · JWT/RBAC")

    st.markdown("### 🔐 Login")
    user = st.text_input("Username", value="admin")
    pwd = st.text_input("Password", type="password", value="admin123")
    if st.button("Login"):
        if _login(user, pwd):
            st.success(f"Logged in as {st.session_state.role}")

    st.divider()
    st.markdown("### ⚙️ Runtime Settings")
    os.environ["RETRIEVAL_MODE"] = st.selectbox("Retrieval", ["hybrid", "dense", "sparse"], index=0)
    os.environ["KG_ENABLED"] = str(st.toggle("Knowledge Graph", True)).lower()
    os.environ["KG_EXTRACTION_MODE"] = st.selectbox("KG Extract", ["hybrid", "rule", "llm"], index=0)
    os.environ["LLM_PROVIDER"] = st.selectbox("LLM Provider", ["ollama", "openai"], index=0)

    st.divider()
    st.markdown("### 📄 Ingest")
    uploads = st.file_uploader("PDF / TXT / MD / DOCX", type=["pdf", "txt", "md", "docx"], accept_multiple_files=True)
    can_ingest = st.session_state.token and st.session_state.role in ("admin", "editor")
    if st.button("🚀 Ingest", disabled=not uploads or not can_ingest):
        with st.spinner("Ingesting..."):
            try:
                result = _ingest(uploads)
                st.session_state.ingested = True
                st.success(f"Chunks: {result.get('chunks_created', 0)}, KG triples: {result.get('kg_triples', 0)}")
            except Exception as e:
                st.error(str(e))

    st.divider()
    if st.session_state.role == "admin" and st.session_state.thread_id and st.session_state.token:
        st.markdown("### 🛑 HITL Admin")
        if st.button("✅ Approve pending"):
            r = httpx.post(
                f"{_api_base()}/hitl/resume",
                json={"thread_id": st.session_state.thread_id, "approved": True},
                headers=_auth_headers(),
                timeout=120,
            )
            st.json(r.json())

    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.session_state.metrics = []
        st.session_state.conversation_id = None
        st.session_state.thread_id = None
        st.rerun()

    if st.session_state.token and st.session_state.conversation_id:
        if st.button("🔄 Reload history from server"):
            try:
                _load_messages_from_api(st.session_state.conversation_id)
                st.success("History reloaded")
            except Exception as e:
                st.error(str(e))

st.markdown("# 🏭 Production RAG Agent")
st.caption(
    f"Env: **{os.getenv('APP_ENV', 'local')}** · "
    f"Role: **{st.session_state.role}** · "
    f"Retrieval: **{os.environ.get('RETRIEVAL_MODE')}**"
)

if not st.session_state.token:
    st.warning("请先在侧边栏登录（默认 admin / admin123），并确保 API 服务已启动。")

if not st.session_state.ingested:
    st.info("Upload documents in the sidebar, or ingest via CLI.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander("📎 Metadata"):
                st.write(msg.get("meta", {}))

if prompt := st.chat_input("Ask about your knowledge base...", disabled=not st.session_state.token):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        meta = {}

        try:
            data = _chat(prompt)
            full = data.get("answer", "")
            meta = data
            st.session_state.conversation_id = data.get("conversation_id") or st.session_state.conversation_id
            st.session_state.thread_id = data.get("thread_id") or st.session_state.conversation_id
            if data.get("hitl_pending"):
                st.warning("⏸ HITL pending — admin approval required")
            placeholder.markdown(full)
        except Exception as e:
            full = f"⚠️ Error: {e}"
            placeholder.markdown(full)

        with st.expander("📎 Metadata"):
            st.json({k: meta.get(k) for k in ("sources", "latency_ms", "grade", "conflicts", "hitl_pending", "request_id") if meta.get(k) is not None})

    st.session_state.messages.append({"role": "assistant", "content": full, "meta": meta})
    if meta.get("latency_ms"):
        st.session_state.metrics.append({"latency_ms": meta["latency_ms"]})
