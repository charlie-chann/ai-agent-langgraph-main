"""
app.py — Streamlit 人机界面（project_00_rag_agent）

【职责】
提供可视化聊天、文档上传、运行时配置与 HITL 审批入口。

【两种运行模式】
1. Local（默认）：进程内直接 import agent / ingest，适合本地开发与离线演示
2. API：通过 httpx 调用 FastAPI 后端，适合前后端分离或远程部署

【侧边栏能力】
- JWT 登录（API 模式）或本地角色选择（ACL 演示）
- 检索模式、KG 开关、LLM Provider 等环境变量热切换
- 多文件 ingest（admin/editor 或 Local 模式）
- Admin HITL 批准挂起线程
- 清空会话与指标

【与 api.py 的关系】
app 是「壳」；核心业务在 agent.py + tools/*；API 模式时 app 仅为 HTTP 客户端。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import streamlit as st

st.set_page_config(
    page_title="Production RAG Agent",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session 默认值 ────────────────────────────────────────────────────────────
# Streamlit 刷新页面时 session_state 持久化；此处仅首次访问时初始化
for key, default in [
    ("messages", []),       # UI 展示用消息（与 DB 同步）
    ("metrics", []),
    ("token", None),
    ("role", "viewer"),
    ("conversation_id", None),  # 服务端会话 ID（API 模式）
    ("thread_id", None),    # 与 conversation_id 对齐，HITL 用
    ("use_api", False),
    ("ingested", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _api_base() -> str:
    """FastAPI 基地址，可通过环境变量 API_BASE_URL 覆盖。"""
    return os.getenv("API_BASE_URL", "http://localhost:8000")


def _login(username: str, password: str) -> bool:
    """
    API 模式登录：POST /auth/token，成功则写入 session token 与 role。
    """
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
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _ensure_conversation_api() -> str:
    """API 模式：确保有 conversation_id，没有则向服务端创建。"""
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
    """从服务端拉取会话消息，刷新 UI 展示。"""
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


def _chat_api(message: str) -> dict:
    """
    API 模式：只发 message，chat_history 由服务端 PostgreSQL/SQLite 加载。
    """
    cid = _ensure_conversation_api()
    r = httpx.post(
        f"{_api_base()}/conversations/{cid}/chat",
        json={"message": message},
        headers=_auth_headers(),
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def _chat_local(message: str):
    """
    Local 模式流式问答：使用 session 内多轮历史（进程内，不经 DB）。
    """
    from agent import ask_stream
    from core.compression import dict_history_to_messages

    history = dict_history_to_messages(
        [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
    )
    for token in ask_stream(message, history, user_roles=[st.session_state.role, "public"]):
        yield token


def _ingest_local(files) -> dict:
    """
    Local 模式文档摄入：校验后写临时目录，再 ingest_files。
    """
    from tools.ingest import ingest_files, validate_upload

    tmp = Path("/tmp/rag_uploads_ui")
    tmp.mkdir(exist_ok=True)
    saved = []
    for f in files:
        validate_upload(f.name, f.size)
        dest = tmp / f.name
        dest.write_bytes(f.getvalue())
        saved.append(dest)
    return ingest_files(saved, acl_roles=[st.session_state.role, "public"])


def _ingest_api(files) -> dict:
    """
    API 模式文档摄入：multipart 上传至 POST /ingest。
    """
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    multipart = [("files", (f.name, f.getvalue(), f.type or "application/octet-stream")) for f in files]
    r = httpx.post(f"{_api_base()}/ingest", files=multipart, headers=headers, timeout=300)
    r.raise_for_status()
    return r.json()


# ══════════════════════════════════════════════════════════════════════════════
# 侧边栏：模式切换、登录、运行时配置、ingest、HITL、清空会话
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏭 Production RAG")
    st.caption("Hybrid · KG · HITL · JWT/RBAC")

    st.session_state.use_api = st.toggle("Use API backend", value=st.session_state.use_api)

    if st.session_state.use_api:
        st.markdown("### 🔐 Login")
        user = st.text_input("Username", value="admin")
        pwd = st.text_input("Password", type="password", value="admin123")
        if st.button("Login"):
            if _login(user, pwd):
                st.success(f"Logged in as {st.session_state.role}")
    else:
        # Local 模式无 JWT，用 selectbox 模拟不同 ACL 角色
        st.session_state.role = st.selectbox("Local role (ACL)", ["admin", "editor", "viewer"], index=2)

    st.divider()
    st.markdown("### ⚙️ Runtime Settings")
    # 写入 os.environ，config/settings 在下次 agent 调用时读取
    os.environ["RETRIEVAL_MODE"] = st.selectbox("Retrieval", ["hybrid", "dense", "sparse"], index=0)
    os.environ["KG_ENABLED"] = str(st.toggle("Knowledge Graph", True)).lower()
    os.environ["KG_EXTRACTION_MODE"] = st.selectbox("KG Extract", ["hybrid", "rule", "llm"], index=0)
    os.environ["LLM_PROVIDER"] = st.selectbox("LLM Provider", ["ollama", "openai"], index=0)

    st.divider()
    st.markdown("### 📄 Ingest")
    uploads = st.file_uploader("PDF / TXT / MD / DOCX", type=["pdf", "txt", "md", "docx"], accept_multiple_files=True)
    can_ingest = st.session_state.role in ("admin", "editor") or not st.session_state.use_api
    if st.button("🚀 Ingest", disabled=not uploads or not can_ingest):
        with st.spinner("Ingesting..."):
            try:
                result = _ingest_api(uploads) if st.session_state.use_api else _ingest_local(uploads)
                st.session_state.ingested = True
                st.success(f"Chunks: {result.get('chunks_created', 0)}, KG triples: {result.get('kg_triples', 0)}")
            except Exception as e:
                st.error(str(e))

    st.divider()
    # 仅 admin 且已有 thread_id 时展示 HITL 批准按钮
    if st.session_state.role == "admin" and st.session_state.thread_id:
        st.markdown("### 🛑 HITL Admin")
        if st.button("✅ Approve pending"):
            if st.session_state.use_api and st.session_state.token:
                r = httpx.post(
                    f"{_api_base()}/hitl/resume",
                    json={"thread_id": st.session_state.thread_id, "approved": True},
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                    timeout=120,
                )
                st.json(r.json())
            else:
                from agent import resume_hitl
                st.json(resume_hitl(st.session_state.thread_id, approved=True))

    if st.button("🗑️ Clear chat"):
        st.session_state.messages = []
        st.session_state.metrics = []
        st.session_state.conversation_id = None
        st.session_state.thread_id = None
        st.rerun()

    if st.session_state.use_api and st.session_state.token and st.session_state.conversation_id:
        if st.button("🔄 Reload history from server"):
            try:
                _load_messages_from_api(st.session_state.conversation_id)
                st.success("History reloaded")
            except Exception as e:
                st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# 主区域：历史消息渲染 + 聊天输入
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("# 🏭 Production RAG Agent")
mode = "API" if st.session_state.use_api else "Local"
st.caption(f"Mode: **{mode}** · Role: **{st.session_state.role}** · Retrieval: **{os.environ.get('RETRIEVAL_MODE')}**")

if not st.session_state.ingested:
    st.info("Upload documents in the sidebar, or ingest via CLI.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander("📎 Metadata"):
                st.write(msg.get("meta", {}))

if prompt := st.chat_input("Ask about your knowledge base..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        meta = {}

        try:
            if st.session_state.use_api and st.session_state.token:
                # API 模式：一次性返回完整答案与 metadata
                data = _chat_api(prompt)
                full = data.get("answer", "")
                meta = data
                st.session_state.conversation_id = data.get("conversation_id") or st.session_state.conversation_id
                st.session_state.thread_id = data.get("thread_id") or st.session_state.conversation_id
                if data.get("hitl_pending"):
                    st.warning("⏸ HITL pending — admin approval required")
                placeholder.markdown(full)
            else:
                # Local 模式：流式 token + 末尾 __META__ JSON
                for token in _chat_local(prompt):
                    if token.startswith("\n\n__META__"):
                        meta = json.loads(token.replace("\n\n__META__", ""))
                    else:
                        full += token
                        placeholder.markdown(full + "▌")
                placeholder.markdown(full)
        except Exception as e:
            full = f"⚠️ Error: {e}"
            placeholder.markdown(full)

        with st.expander("📎 Metadata"):
            st.json({k: meta.get(k) for k in ("sources", "latency_ms", "grade", "conflicts", "hitl_pending", "request_id") if meta.get(k) is not None})

    st.session_state.messages.append({"role": "assistant", "content": full, "meta": meta})
    if meta.get("latency_ms"):
        st.session_state.metrics.append({"latency_ms": meta["latency_ms"]})
