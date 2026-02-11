# app.py — 量化金融分析 Agent Streamlit UI
#
# 【功能】
#   Tab1 股票分析  → analyze_stock()（技术指标 + 可选基本面）
#   Tab2 组合风险  → compute_portfolio()（夏普/VaR/最大回撤）
#   Tab3 AI 研报   → generate_research_report()（LLM 生成报告）
import json
import streamlit as st

st.set_page_config(
    page_title="📈 Quant Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import DEFAULT_MODEL, OLLAMA_BASE_URL
from agent import analyze_stock, compute_portfolio, generate_research_report


def _mock_prices(n: int = 60, start: float = 100.0, trend: float = 0.3) -> list[float]:
    """生成演示用价格序列（无实时行情数据源时使用）。"""
    prices = [start]
    for i in range(1, n):
        prices.append(round(prices[-1] + trend + (i % 3 - 1) * 0.2, 2))
    return prices


with st.sidebar:
    st.markdown("## 📈 Quant Agent")
    st.caption("技术指标 · 基本面 · 组合风险 · AI 研报")
    st.divider()
    st.markdown(f"**模型:** `{DEFAULT_MODEL}`")
    st.caption(f"Ollama: `{OLLAMA_BASE_URL}`")
    st.divider()
    st.warning("仅供学习研究，不构成投资建议。")

st.title("📈 量化金融分析 Agent")
st.caption("SMA/RSI/MACD · 基本面估值 · 夏普比率/VaR · LLM 投研报告")

tab1, tab2, tab3 = st.tabs(["📊 股票分析", "🛡️ 组合风险", "📝 AI 研报"])

with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker = st.text_input("股票代码", value="AAPL", placeholder="AAPL").upper().strip()
        use_mock = st.checkbox("使用演示价格数据", value=True)
        include_fund = st.checkbox("包含基本面分析", value=True)
    with col2:
        prices_text = st.text_area(
            "收盘价序列（逗号分隔，留空则用演示数据）",
            placeholder="100, 101.5, 99.8, ...",
            height=80,
        )

    if st.button("🔍 运行分析", type="primary"):
        try:
            if use_mock or not prices_text.strip():
                closes = _mock_prices(60, start=150.0, trend=0.25)
            else:
                closes = [float(x.strip()) for x in prices_text.split(",") if x.strip()]

            fundamentals = None
            if include_fund:
                fundamentals = {
                    "eps": 6.5, "bvps": 4.2, "eps_prev": 5.8,
                    "revenue_current": 380, "revenue_prev": 350,
                    "total_equity": 60, "net_income": 95,
                    "total_debt": 110, "fcf": 85, "dividend": 0.96,
                }

            with st.spinner("计算技术指标..."):
                result = analyze_stock(ticker, closes, fundamentals=fundamentals)

            st.success(f"分析完成 ({result['latency_ms']}ms)")
            tech = result["technical"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("收盘价", f"{tech.get('close_price', 0):.2f}")
            c2.metric("趋势", tech.get("trend", "neutral"))
            c3.metric("RSI(14)", f"{tech.get('rsi_14') or 'N/A'}")
            c4.metric("SMA20", f"{tech.get('sma_20') or 'N/A'}")

            if tech.get("signals"):
                st.markdown("**技术信号**")
                for sig in tech["signals"]:
                    st.markdown(f"- {sig}")

            with st.expander("完整技术数据", expanded=False):
                st.json(tech)

            if result.get("fundamental"):
                with st.expander("基本面数据", expanded=True):
                    st.json(result["fundamental"])

            st.session_state["last_analysis"] = result
            st.session_state["last_ticker"] = ticker
        except Exception as e:
            st.error(f"分析失败: {e}")

with tab2:
    st.markdown("输入日收益率序列（小数形式，如 0.01 表示 +1%）")
    returns_text = st.text_input(
        "收益率",
        value="0.01,-0.005,0.008,-0.012,0.003,0.015,-0.008,0.006,0.002,-0.004",
    )
    if st.button("📉 计算组合风险", type="primary"):
        try:
            returns = [float(x.strip()) for x in returns_text.split(",") if x.strip()]
            result = compute_portfolio(returns)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("夏普比率", result.get("sharpe_ratio", "N/A"))
            c2.metric("最大回撤", f"{(result.get('max_drawdown') or 0)*100:.2f}%")
            c3.metric("年化波动率", f"{(result.get('annual_volatility') or 0)*100:.2f}%")
            c4.metric("风险等级", result.get("risk_level", "N/A"))
            with st.expander("完整风险指标"):
                st.json(result)
        except Exception as e:
            st.error(f"计算失败: {e}")

with tab3:
    st.markdown("基于「股票分析」Tab 的结果，调用 LLM 生成 Markdown 投研报告。")
    if "last_analysis" not in st.session_state:
        st.info("请先在「股票分析」Tab 运行一次分析。")
    elif st.button("📝 生成 AI 研报", type="primary"):
        ticker = st.session_state.get("last_ticker", "STOCK")
        analysis = st.session_state["last_analysis"]
        with st.spinner("LLM 生成报告中..."):
            report = generate_research_report(ticker, analysis)
        st.markdown(report)
