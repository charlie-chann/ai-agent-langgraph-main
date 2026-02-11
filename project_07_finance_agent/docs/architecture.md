# docs/architecture.md — Finance Agent Architecture

## System Architecture

```
User (Streamlit / API)
         │
         ▼
  ┌─────────────────┐
  │  ReAct Agent    │  ← qwen3.5:latest via Ollama
  │  (LangChain)    │
  └────────┬────────┘
           │  Tool dispatch
  ┌────────┴──────────────────────────────────────┐
  │                                               │
  ▼              ▼               ▼                ▼
market_data   news_tool     analysis_tool    compliance_tool
(yfinance)  (DuckDuckGo)   (pure Python)     (rule-based)
  │              │               │                │
  ▼              ▼               ▼                ▼
Real prices   Web search     DCF, ratios      Position limits
Financials    Headlines      Score cards      ESG screening
History       Sector news    Portfolio risk   Sector limits
                                               ▼
                                          report_tool
                                          (save to disk)
```

## Agent Tool Set (15 tools)

| Tool | Source | Description |
|------|--------|-------------|
| `get_stock_quote` | yfinance | Live price, PE, PB, beta, analyst target |
| `get_financials` | yfinance | Revenue, margins, ROE, D/E, FCF |
| `get_price_history` | yfinance | OHLCV + MA20/50/200 + annualised vol |
| `compare_stocks` | yfinance | Multi-ticker side-by-side comparison |
| `get_financial_news` | DuckDuckGo | Company/topic news search |
| `get_sector_news` | DuckDuckGo | Sector outlook articles |
| `calculate_dcf` | Pure Python | DCF intrinsic value projection |
| `analyse_fundamentals` | Pure Python | Scored quality analysis (9 metrics) |
| `calculate_portfolio_metrics` | Pure Python | Portfolio beta, sector weights |
| `check_position_compliance` | Rule-based | Single position audit |
| `screen_portfolio_compliance` | Rule-based | Full portfolio compliance |
| `get_compliance_rules` | Config | Active rule thresholds |
| `save_report` | Disk | OHLCV + Markdown report |
| `list_reports` | Disk | List saved reports |
| `read_report` | Disk | Read saved report |

## Data Flow

```
User Query → Agent Reasoning → Tool Selection
                ↓
        [yfinance / DuckDuckGo / Pure Python]
                ↓
        Structured JSON results
                ↓
        Agent synthesises → Final analysis
                ↓
        (optional) save_report → reports/*.md
```

## Compliance Rule Engine

Rules are configurable via `.env` or `config.py`:
- `MAX_POSITION_WEIGHT`: single position cap (default 20%)
- `VOLATILITY_WARN_THRESHOLD`: annual vol warning level (default 40%)
- `RISK_FREE_RATE`: discount baseline (default 5%)
- ESG exclusion list: tobacco, weapons, gambling, fossil fuel pure-play
