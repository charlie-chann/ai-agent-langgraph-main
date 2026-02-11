"""app.py — Streamlit UI for Code / DevOps Agent (project_06)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from loguru import logger

from config import OLLAMA_BASE_URL, CODE_MODEL, DEFAULT_MODEL, SANDBOX_DIR

st.set_page_config(
    page_title="⚙️ Code Agent",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Code / DevOps Agent")
    st.caption("AI-powered code generation, review & execution")
    st.divider()

    model = st.selectbox(
        "Model",
        [CODE_MODEL, DEFAULT_MODEL, "qwen2.5-coder:7b", "codellama"],
        index=0,
    )
    st.caption(f"Ollama: `{OLLAMA_BASE_URL}`")
    st.divider()

    mode = st.radio(
        "Mode",
        ["💬 Chat Agent", "⚡ Quick Execute", "🔍 Code Review"],
        index=0,
    )
    st.divider()

    st.markdown("**Sandbox workspace**")
    sandbox = Path(SANDBOX_DIR)
    if sandbox.exists():
        files = list(sandbox.rglob("*"))
        code_files = [f for f in files if f.is_file()]
        st.caption(f"{len(code_files)} files in sandbox")
        if code_files:
            with st.expander("Files"):
                for f in sorted(code_files)[:20]:
                    st.code(str(f.relative_to(sandbox.resolve())), language=None)
    else:
        st.caption("Sandbox not yet created")

    if st.button("🗑 Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ── Main area ──────────────────────────────────────────────────────────────
st.title("⚙️ Code Agent")
st.caption("Write, execute, review, and debug code — powered by local LLM")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Render history ─────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("steps"):
            with st.expander("🔧 Tool calls", expanded=False):
                for i, (action, obs) in enumerate(msg["steps"], 1):
                    st.markdown(f"**Step {i}:** `{action.tool}` ← `{action.tool_input}`")
                    st.code(str(obs)[:800], language=None)

# ── Quick Execute mode ─────────────────────────────────────────────────────
if mode == "⚡ Quick Execute":
    st.markdown("### Run Python Code")
    code_input = st.text_area("Code", height=200, placeholder="print('Hello, world!')")
    if st.button("▶ Run"):
        from tools.code_executor import execute_python
        with st.spinner("Executing…"):
            result = execute_python.invoke(code_input)
        st.markdown("**Output:**")
        st.code(result, language=None)

# ── Code Review mode ──────────────────────────────────────────────────────
elif mode == "🔍 Code Review":
    st.markdown("### Review Code")
    lang = st.selectbox("Language", ["python", "javascript", "typescript", "go", "java"])
    code_input = st.text_area("Paste code to review", height=300)
    if st.button("🔍 Review"):
        from tools.code_reviewer import review_code
        with st.spinner("Reviewing…"):
            result = review_code.invoke({"code": code_input, "language": lang})
        st.markdown(result)

# ── Chat Agent mode ───────────────────────────────────────────────────────
else:
    examples = [
        "Write a Python function that parses JSON safely and handles all edge cases",
        "Create a Dockerfile for a Python FastAPI app",
        "Write and run a quicksort implementation, then explain its complexity",
        "Generate a GitHub Actions CI workflow for a Python project",
        "Review this code and find bugs: `def div(a,b): return a/b`",
    ]
    with st.expander("💡 Example prompts"):
        for ex in examples:
            if st.button(ex, key=ex):
                st.session_state._prefill = ex

    prompt = st.chat_input("Ask the code agent…")
    if not prompt and st.session_state.get("_prefill"):
        prompt = st.session_state.pop("_prefill")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            container = st.empty()
            steps_placeholder = st.empty()

            try:
                from agent import build_agent
                executor = build_agent(model)
                result = executor.invoke({"input": prompt})
                output = result.get("output", "")
                steps = result.get("intermediate_steps", [])

                container.markdown(output)
                if steps:
                    with steps_placeholder.expander(f"🔧 {len(steps)} tool call(s)", expanded=False):
                        for i, (action, obs) in enumerate(steps, 1):
                            st.markdown(f"**Step {i}:** `{action.tool}`")
                            st.code(f"Input: {action.tool_input}\n\nOutput: {str(obs)[:600]}", language=None)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": output,
                    "steps": steps,
                })

            except Exception as e:
                err = f"❌ Agent error: {e}"
                container.error(err)
                logger.error(f"[app] {e}")
                st.session_state.messages.append({"role": "assistant", "content": err})
