# docs/index.md — Project 06: Code / DevOps Agent

## Index

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System design, agent graph, tool flow |
| [API Reference](api_reference.md) | REST + SSE endpoints |
| [Evaluation](evaluation.md) | Benchmark results & quality metrics |
| [Changelog](changelog.md) | Version history |

---

## Project Overview

**Code / DevOps Agent** is an AI assistant that writes, executes, reviews, and debugs code directly in your browser. Built on LangChain ReAct + local Ollama LLM (`qwen2.5-coder`), it provides a private, zero-cloud-cost alternative to GitHub Copilot Chat for teams working with sensitive codebases.

### Core capabilities
- **Code generation** — Python, JavaScript, Bash, Dockerfile, CI/CD YAML
- **Safe sandbox execution** — runs Python code in an isolated subprocess with timeout + import blocking
- **AI code review** — OWASP-aware security analysis, performance hints, style feedback
- **File management** — read/write files in a sandboxed workspace
- **Git integration** — status, log, diff, and commit via subprocess

### Quick start
```bash
cd project_06_code_agent
cp .env.example .env
uv run streamlit run app.py
```

### Run tests
```bash
uv run pytest tests/ -v
```
