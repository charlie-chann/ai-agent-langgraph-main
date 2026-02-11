# Changelog — project_04_deep_research

## v1.0.0 — 2026-03-18
- Initial release
- LangGraph iterative loop: QueryGen → Search → Synthesize → GapAnalysis (→ repeat or write)
- Coverage-based routing (threshold=0.8, max 4 rounds)
- Auto-save reports to ./reports/
- Streamlit UI with live progress, coverage metrics, download
- FastAPI SSE + REST endpoints
- 7 unit tests
