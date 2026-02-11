# Changelog — project_03_multi_agent

## v1.0.0 — 2026-03-18
- Initial release
- LangGraph 5-node pipeline: Planner → Researcher → Writer → Critic → Summarizer
- Two scenarios: Market Research Report + Social Media Content
- Auto-revision loop: Critic score < 7 triggers Writer retry (max 2×)
- Streamlit UI with live agent progress, metrics, download button
- FastAPI SSE + REST endpoints
