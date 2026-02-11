# docs/changelog.md — Finance Agent Changelog

## v1.0.0 (Initial Release)

### Added
- Real-time stock data via yfinance (free, no API key)
- 4 market data tools: quote, financials, price history, multi-stock compare
- 2 news tools: company news, sector news (DuckDuckGo)
- 3 analysis tools: DCF valuation, fundamentals scorer, portfolio metrics
- 3 compliance tools: position check, portfolio screening, rule viewer
- 3 report tools: save, list, read Markdown reports
- Streamlit 4-mode UI: Research Chat, Quick Quote, Compliance Check, Reports
- Interactive Plotly candlestick charts
- FastAPI SSE API on port 8007
- 17 unit tests (all passing, no external deps required)

## Planned (v1.1.0)
- PDF report export (ReportLab or WeasyPrint)
- Earnings calendar integration
- Options data (puts/calls IV, Greeks)
- Backtesting support (portfolio performance vs benchmark)
- Multi-language support (Chinese financial market tickers: e.g. 0700.HK)
- Webhook alerts for compliance violations
