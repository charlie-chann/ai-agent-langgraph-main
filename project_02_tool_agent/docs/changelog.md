# Changelog — project_02_tool_agent

## v1.0.0 — 2026-03-18
- Initial release
- Tools: web_search (DuckDuckGo), calculator (safe AST), file_read/write/list (sandboxed), get_datetime
- LangChain ReAct agent with max 8 iterations
- Streamlit UI with tool-call expander
- FastAPI SSE + REST endpoints
- Security: path traversal protection, calculator injection guard
