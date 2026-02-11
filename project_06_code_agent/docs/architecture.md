# docs/architecture.md — Code Agent Architecture

## System Architecture

```
User (Streamlit / API)
         │
         ▼
   ┌───────────────┐
   │  ReAct Agent  │ ← qwen2.5-coder via Ollama
   │  (LangChain)  │
   └──────┬────────┘
          │  Tool dispatch
    ┌─────┴──────────────────────────────────┐
    │                                        │
    ▼                     ▼                  ▼
execute_python        review_code      file_tool
lint_python           (LLM-powered)    git_tool
    │                                        │
    ▼                                        ▼
Sandboxed subprocess              SANDBOX_DIR (local FS)
(tempfile + timeout)              Path traversal blocked
```

## Agent Loop

1. User submits a coding task
2. ReAct agent reasons about which tool(s) to call
3. Tools execute and return observations
4. Agent continues reasoning until task is complete
5. Final answer returned to user

## Security Model

| Layer | Protection |
|-------|-----------|
| Static analysis | `_is_safe()` blocks `import os/sys/subprocess`, `eval`, `exec`, `open`, network libs |
| Subprocess isolation | Code runs in a child process with `cwd=SANDBOX_DIR`, `timeout=10s` |
| File sandbox | All file operations restricted to `SANDBOX_DIR`; path traversal detection |
| Prompt hygiene | User input passed through LangChain input validation |
