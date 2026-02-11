"""app.py — Streamlit UI for Finance / Compliance Analysis Agent (project_07)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
import streamlit as st
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, REPORTS_DIR

st.set_page_config(
    page_title="📈 Finance Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📈 Finance Agent")
    st.caption("AI-powered stock research, portfolio compliance & reporting")
    st.divider()

    model = st.selectbox("LLM Model", [DEFAULT_MODEL, "qwen3.5:7b", "llama3.1"], index=0)
    st.caption(f"Ollama: `{OLLAMA_BASE_URL}`")
    st.divider()

    mode = st.radio(
        "Mode",
        ["💬 Research Chat", "📊 Quick Quote", "🛡 Compliance Check", "📋 Reports"],
        index=0,
    )
    st.divider()

    with st.expander("ℹ️ Disclaimer"):
        st.caption(
            "This tool is for informational and educational purposes only. "
            "It does not constitute financial or investment advice. "
            "Always consult a licensed financial advisor before making investment decisions."
        )

    if st.button("🗑 Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# ── Load Plotly lazily ─────────────────────────────────────────────────────────
def _try_import_plotly():
    try:
        import plotly.graph_objects as go
        return go
    except ImportError:
        return None

# ── Main ───────────────────────────────────────────────────────────────────────
st.title("📈 Finance & Compliance Agent")
st.caption("Real-time stock data · Fundamental analysis · Portfolio compliance · AI-generated reports")

# ── QUICK QUOTE TAB ────────────────────────────────────────────────────────────
if mode == "📊 Quick Quote":
    col1, col2 = st.columns([2, 1])
    with col1:
        ticker_input = st.text_input("Ticker Symbol", placeholder="AAPL, MSFT, 0700.HK …").upper().strip()
    with col2:
        period = st.selectbox("History Period", ["3mo", "6mo", "1y", "2y"], index=2)

    if st.button("🔍 Fetch Data") and ticker_input:
        from tools.market_data import get_stock_quote, get_price_history, get_financials

        col_q, col_h = st.columns(2)

        with col_q:
            with st.spinner("Fetching quote…"):
                quote_raw = get_stock_quote.invoke(ticker_input)
            try:
                q = json.loads(quote_raw)
                st.subheader(f"{q.get('name', ticker_input)}")
                price = q.get("price")
                change = q.get("change_pct")
                delta_str = f"{change:+.2f}%" if change is not None else "N/A"
                st.metric("Price", f"${price:.2f}" if price else "N/A", delta_str)

                metrics_data = {
                    "P/E Ratio": q.get("pe_ratio"),
                    "P/B Ratio": q.get("pb_ratio"),
                    "Beta": q.get("beta"),
                    "Div Yield": f"{q.get('dividend_yield',0)*100:.2f}%" if q.get("dividend_yield") else "N/A",
                    "52W High": q.get("52w_high"),
                    "52W Low": q.get("52w_low"),
                    "Analyst Target": q.get("analyst_target"),
                    "Recommendation": q.get("recommendation", "N/A").upper(),
                }
                for label, val in metrics_data.items():
                    st.write(f"**{label}**: {val}")
            except Exception:
                st.code(quote_raw)

        with col_h:
            with st.spinner("Fetching history…"):
                hist_raw = get_price_history.invoke({"ticker": ticker_input, "period": period})
            try:
                h = json.loads(hist_raw)
                st.subheader("Price History")
                cols = st.columns(2)
                cols[0].metric("Period Return", f"{h.get('period_return_pct', 0):.1f}%")
                cols[1].metric("Annualised Vol", f"{(h.get('annualised_volatility',0) or 0)*100:.1f}%")
                st.write(f"**MA20**: {h.get('ma_20')}  **MA50**: {h.get('ma_50')}  **MA200**: {h.get('ma_200', 'N/A')}")
                st.write(f"**Trend**: {h.get('trend', 'N/A').capitalize()}")

                # Try to draw a price chart using yfinance
                go = _try_import_plotly()
                if go:
                    try:
                        import yfinance as yf
                        df = yf.Ticker(ticker_input).history(period=period)
                        if not df.empty:
                            fig = go.Figure()
                            fig.add_trace(go.Candlestick(
                                x=df.index,
                                open=df["Open"], high=df["High"],
                                low=df["Low"], close=df["Close"],
                                name=ticker_input,
                            ))
                            fig.update_layout(
                                title=f"{ticker_input} — {period}",
                                xaxis_rangeslider_visible=False,
                                height=350,
                                margin=dict(l=0, r=0, t=40, b=0),
                                template="plotly_dark",
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        pass
            except Exception:
                st.code(hist_raw)

        st.divider()
        with st.spinner("Fetching financials…"):
            fin_raw = get_financials.invoke(ticker_input)
        try:
            f = json.loads(fin_raw)
            st.subheader("Financials")
            cols = st.columns(3)
            cols[0].metric("Revenue TTM", f"${f.get('revenue_ttm',0)/1e9:.1f}B" if f.get('revenue_ttm') else "N/A")
            cols[1].metric("Net Margin", f"{(f.get('net_margin',0) or 0)*100:.1f}%")
            cols[2].metric("ROE", f"{(f.get('return_on_equity',0) or 0)*100:.1f}%")

            st.write(f"**Gross Margin**: {(f.get('gross_margin',0) or 0)*100:.1f}%  "
                     f"**D/E**: {f.get('debt_to_equity','N/A')}  "
                     f"**Current Ratio**: {f.get('current_ratio','N/A')}  "
                     f"**Revenue Growth**: {(f.get('revenue_growth',0) or 0)*100:.1f}%")
        except Exception:
            st.code(fin_raw)

# ── COMPLIANCE TAB ─────────────────────────────────────────────────────────────
elif mode == "🛡 Compliance Check":
    st.subheader("Portfolio Compliance Screening")
    st.caption("Paste your portfolio as JSON to run automated compliance checks")

    example = json.dumps([
        {"ticker": "AAPL", "weight": 0.20, "sector": "Technology", "volatility": 0.28},
        {"ticker": "MSFT", "weight": 0.18, "sector": "Technology", "volatility": 0.25},
        {"ticker": "JPM",  "weight": 0.12, "sector": "Financial Services", "volatility": 0.30},
        {"ticker": "JNJ",  "weight": 0.10, "sector": "Healthcare", "volatility": 0.18},
        {"ticker": "XOM",  "weight": 0.08, "sector": "Energy", "volatility": 0.32},
        {"ticker": "AMZN", "weight": 0.15, "sector": "Consumer Cyclical", "volatility": 0.35},
        {"ticker": "BRK-B","weight": 0.17, "sector": "Financial Services", "volatility": 0.22},
    ], indent=2)

    portfolio_input = st.text_area("Portfolio JSON", value=example, height=280)

    if st.button("🛡 Run Compliance Check"):
        from tools.compliance_tool import screen_portfolio_compliance, get_compliance_rules
        from tools.analysis_tool import calculate_portfolio_metrics

        with st.spinner("Running compliance screening…"):
            compliance_raw = screen_portfolio_compliance.invoke(portfolio_input)
            portfolio_raw = calculate_portfolio_metrics.invoke(portfolio_input)
            rules_raw = get_compliance_rules.invoke(None)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Compliance Report")
            try:
                c = json.loads(compliance_raw)
                status = c.get("overall_status", "")
                if "✅" in status:
                    st.success(status)
                elif "❌" in status:
                    st.error(status)
                else:
                    st.warning(status)

                for v in c.get("violations", []):
                    st.error(v)
                for w in c.get("warnings", []):
                    st.warning(w)
                for p in c.get("passed_checks", []):
                    st.success(p)
            except Exception:
                st.code(compliance_raw)

        with col2:
            st.subheader("Portfolio Metrics")
            try:
                p = json.loads(portfolio_raw)
                st.metric("Portfolio Beta", p.get("portfolio_beta", "N/A"))
                st.metric("Positions", p.get("num_positions", 0))
                st.metric("Diversification Score", f"{p.get('diversification_score',0)}/10")
                st.write("**Sector Allocation:**")
                for sector, pct in p.get("sector_allocation", {}).items():
                    st.write(f"  • {sector}: {pct}")
                for w in p.get("warnings", []):
                    st.warning(w)
            except Exception:
                st.code(portfolio_raw)

# ── REPORTS TAB ────────────────────────────────────────────────────────────────
elif mode == "📋 Reports":
    st.subheader("Saved Research Reports")
    from tools.report_tool import list_reports, read_report
    reports_raw = list_reports.invoke(None)
    try:
        reports = json.loads(reports_raw)
        if not reports:
            st.info("No reports saved yet. Run a Research Chat analysis and ask the agent to save a report.")
        else:
            selected = st.selectbox("Select report", [r["filename"] for r in reports])
            st.caption(f"Size: {next(r['size_kb'] for r in reports if r['filename'] == selected)} KB")
            if st.button("📖 Open"):
                content = read_report.invoke(selected)
                st.markdown(content)
    except Exception:
        st.code(reports_raw)

# ── CHAT TAB ───────────────────────────────────────────────────────────────────
else:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Example prompts
    examples = [
        "Analyse Apple (AAPL) — give me a full fundamental analysis with buy/sell recommendation",
        "Compare AAPL, MSFT, GOOGL on valuation and growth metrics",
        "What's the latest news on Tesla and how might it affect the stock?",
        "Calculate the DCF value of a company with $5B FCF, 10% growth, 3% terminal growth, 10% discount rate",
        "Check my portfolio compliance: 25% AAPL, 20% MSFT, 15% TSLA, 40% SPY",
        "Give me a sector overview of the AI/semiconductor space",
    ]
    with st.expander("💡 Example queries"):
        for ex in examples:
            if st.button(ex, key=ex):
                st.session_state._prefill = ex

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("steps"):
                with st.expander(f"🔧 {len(msg['steps'])} tool call(s)", expanded=False):
                    for step in msg["steps"]:
                        st.markdown(f"**`{step['tool']}`** ← `{str(step['input'])[:100]}`")
                        st.code(step["output"][:500], language="json")

    prompt = st.chat_input("Ask about any stock, portfolio, or compliance issue…")
    if not prompt and st.session_state.get("_prefill"):
        prompt = st.session_state.pop("_prefill")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            container = st.empty()
            steps_ph = st.empty()

            try:
                from agent import build_agent
                executor = build_agent(model)
                result = executor.invoke({"input": prompt})
                output = result.get("output", "")
                steps = [
                    {"tool": a.tool, "input": a.tool_input, "output": str(o)[:500]}
                    for a, o in result.get("intermediate_steps", [])
                ]

                container.markdown(output)
                if steps:
                    with steps_ph.expander(f"🔧 {len(steps)} tool call(s)", expanded=False):
                        for s in steps:
                            st.markdown(f"**`{s['tool']}`**")
                            st.code(f"Input: {str(s['input'])[:150]}\nOutput: {s['output']}", language=None)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": output,
                    "steps": steps,
                })
                st.caption("⚠️ For informational purposes only. Not investment advice.")

            except Exception as e:
                err = f"❌ Agent error: {e}"
                container.error(err)
                logger.error(f"[app] {e}")
                st.session_state.messages.append({"role": "assistant", "content": err})
