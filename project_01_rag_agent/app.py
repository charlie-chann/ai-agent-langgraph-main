# app.py — Streamlit UI for Enterprise RAG Agent
import json
import time
from pathlib import Path

import streamlit as st

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Enterprise RAG Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports after page config ─────────────────────────────────────────────────
from config import DEFAULT_MODEL, OLLAMA_BASE_URL, TOP_K, RETRIEVAL_MODE
from agent import ask_stream
from tools.ingest import load_documents, split_documents
from tools.retriever import build_vectorstore, load_vectorstore

# ── Session state defaults ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "ingested" not in st.session_state:
    st.session_state.ingested = False
if "metrics" not in st.session_state:
    st.session_state.metrics = []

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📚 Enterprise RAG Agent")
    st.caption("生产级知识库问答 · Hybrid Search · 自校正")
    st.divider()

    st.markdown("### ⚙️ Model Settings")
    model_name = st.text_input("Ollama Model", value=DEFAULT_MODEL)
    top_k = st.slider("Top-K Retrieval", 1, 10, TOP_K)
    retrieval_mode = st.selectbox("Retrieval Mode", ["hybrid", "vector"], index=0 if RETRIEVAL_MODE == "hybrid" else 1)

    st.divider()
    st.markdown("### 📄 Document Ingestion")
    uploaded_files = st.file_uploader(
        "Upload documents (PDF, TXT, MD, DOCX)",
        type=["pdf", "txt", "md", "docx"],
        accept_multiple_files=True,
    )

    if st.button("🚀 Ingest Documents", disabled=not uploaded_files):
        tmp_dir = Path("/tmp/rag_uploads")
        tmp_dir.mkdir(exist_ok=True)
        saved = []
        for f in uploaded_files:
            dest = tmp_dir / f.name
            dest.write_bytes(f.read())
            saved.append(dest)

        with st.spinner("Processing documents..."):
            docs = load_documents(saved)
            chunks = split_documents(docs)
            build_vectorstore(chunks)
            st.session_state.ingested = True

        st.success(f"Ingested {len(chunks)} chunks from {len(saved)} file(s)")

    st.divider()
    st.markdown("### 📊 Session Metrics")
    if st.session_state.metrics:
        total = len(st.session_state.metrics)
        avg_lat = sum(m["latency_ms"] for m in st.session_state.metrics) / total
        st.metric("Queries", total)
        st.metric("Avg Latency", f"{avg_lat:.0f} ms")
    else:
        st.caption("No queries yet")

    if st.button("🗑️ Clear conversation"):
        st.session_state.messages = []
        st.session_state.metrics = []
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("# 📚 Enterprise RAG Agent")
st.caption(f"Powered by **{model_name}** @ {OLLAMA_BASE_URL}  ·  Mode: **{retrieval_mode}**")

if not st.session_state.ingested:
    st.info("👈 Upload and ingest documents in the sidebar to get started.")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "sources" in msg:
            with st.expander("📎 Sources & Metadata"):
                st.write("**Sources:**", ", ".join(msg["sources"]) or "N/A")
                st.write("**Latency:**", f"{msg.get('latency_ms', 0)} ms")

# ── Chat input ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Ask a question about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        sources = []
        latency_ms = 0

        try:
            for token in ask_stream(prompt):
                if token.startswith("\n\n__META__"):
                    raw = token.replace("\n\n__META__", "")
                    meta = json.loads(raw)
                    sources = meta.get("sources", [])
                    latency_ms = meta.get("latency_ms", 0)
                else:
                    full_response += token
                    placeholder.markdown(full_response + "▌")

            placeholder.markdown(full_response)

        except Exception as e:
            full_response = f"⚠️ Error: {e}"
            placeholder.markdown(full_response)

        with st.expander("📎 Sources & Metadata"):
            st.write("**Sources:**", ", ".join(sources) or "N/A")
            st.write("**Latency:**", f"{latency_ms} ms")

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "sources": sources,
        "latency_ms": latency_ms,
    })
    st.session_state.metrics.append({"latency_ms": latency_ms})
