# docs/index.md — Project 07: Finance / Compliance Analysis Agent

## Index

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System design, agent graph, data flow |
| [API Reference](api_reference.md) | REST + SSE endpoints |
| [Evaluation](evaluation.md) | Benchmark results & accuracy metrics |
| [Changelog](changelog.md) | Version history |

---

## Project Overview

**Finance / Compliance Analysis Agent** is a production-grade AI assistant for stock research, fundamental analysis, portfolio compliance screening, and automated report generation. It uses real market data (via yfinance — free, no API key) and runs entirely on local infrastructure with Ollama LLM.

### Core Capabilities
- **Real-time stock quotes** — prices, PE, PB, beta, analyst targets
- **Fundamental analysis** — income statement, balance sheet, ROE, margins, growth
- **DCF valuation** — discounted cash flow with configurable parameters
- **Technical analysis** — moving averages (MA20/50/200), annualised volatility
- **Portfolio compliance** — concentration limits, sector checks, ESG screening
- **Financial news** — DuckDuckGo-powered (no API key required)
- **Report generation** — save structured Markdown reports to disk

### Quick Start
```bash
cd project_07_finance_agent
cp .env.example .env
uv run streamlit run app.py
```

### Run Tests
```bash
uv run pytest tests/ -v
```
