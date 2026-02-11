# docs/changelog.md — Code Agent Changelog

## v1.0.0 (Initial Release)

### Added
- ReAct agent with `qwen2.5-coder` via Ollama
- `execute_python` — sandboxed Python execution (subprocess + static analysis)
- `lint_python` — AST-based syntax and import checker
- `review_code` — LLM-powered code review with OWASP focus
- `read_code_file` / `write_code_file` / `list_workspace_files` — sandboxed file ops
- `git_status` / `git_log` / `git_diff` / `git_init_and_commit` — git tool set
- Streamlit UI with Chat, Quick Execute, and Code Review modes
- FastAPI SSE API on port 8006
- 15 unit tests (all passing)

## Planned (v1.1.0)
- JavaScript execution via Node.js sandbox
- Bash script generation (read-only preview mode)
- Multi-file project context (load entire directory)
- Integration with project_01 RAG for codebase Q&A
