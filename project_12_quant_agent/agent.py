# agent.py — Quant Research Agent
#
# 【架构】无 LangGraph，采用「纯算法 + LLM 报告」两层：
#   1. tools/ 下的纯 Python 函数计算技术指标、基本面、组合风险（不经过 LLM）
#   2. generate_research_report() 把计算结果交给 LLM 生成文字报告
#
# 【执行入口】
#   analyze_stock() / compute_portfolio()  → 同步返回量化指标
#   generate_research_report()             → chain.stream 流式生成报告
from __future__ import annotations

import time
from langchain_ollama import ChatOllama
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.technical_indicators import compute_signals, TechnicalSignals
from tools.fundamental_metrics import compute_fundamental_metrics, FundamentalMetrics
from tools.portfolio_risk import compute_portfolio_risk, PortfolioRisk


def _llm():
    """创建 Ollama LLM 实例，仅用于报告生成阶段。"""
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize_ticker(ticker: str) -> str:
    """清理和验证股票代码，防止非法输入。"""
    import re
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("股票代码不能为空")
    if not re.match(r'^[A-Z0-9.^-]{1,10}$', ticker):
        raise ValueError(f"无效股票代码: {ticker!r}")
    return ticker


def analyze_stock(ticker: str, closes: list[float], highs: list[float] | None = None,
                  lows: list[float] | None = None,
                  fundamentals: dict | None = None) -> dict:
    """
    综合技术面 + 基本面分析。
    纯算法计算，不调用 LLM，毫秒级返回。
    """
    ticker = _sanitize_ticker(ticker)
    t0 = time.perf_counter()

    # 技术面：RSI / MACD / 均线信号等
    tech = compute_signals(ticker, closes, highs, lows)

    # 基本面：PE / ROE / DCF 相关指标（可选）
    fund = None
    if fundamentals:
        try:
            fund = compute_fundamental_metrics(
                ticker=ticker,
                price=closes[-1] if closes else 0,
                eps=fundamentals.get("eps", 1),
                book_value_per_share=fundamentals.get("bvps", 10),
                revenue_current=fundamentals.get("revenue_current", 100),
                revenue_prev=fundamentals.get("revenue_prev", 80),
                eps_current=fundamentals.get("eps", 1),
                eps_prev=fundamentals.get("eps_prev", 0.8),
                total_equity=fundamentals.get("total_equity", 500),
                net_income=fundamentals.get("net_income", 50),
                total_debt=fundamentals.get("total_debt", 200),
                free_cash_flow=fundamentals.get("fcf", 30),
                dividend_per_share=fundamentals.get("dividend", 0),
            )
        except Exception as e:
            logger.warning(f"基本面计算失败: {e}")

    elapsed = round((time.perf_counter() - t0) * 1000)
    return {
        "ticker": ticker,
        "technical": tech.to_dict(),
        "fundamental": fund.to_dict() if fund else {},
        "latency_ms": elapsed,
    }


def compute_portfolio(returns: list[float], benchmark_returns: list[float] | None = None) -> dict:
    """计算投资组合风险指标（夏普比率、VaR、最大回撤等），纯算法。"""
    risk = compute_portfolio_risk(returns, benchmark_returns)
    return risk.to_dict()


def generate_research_report(ticker: str, analysis: dict) -> str:
    """使用 LLM 把量化数据转成可读投研报告（chain.stream 流式生成）。"""
    from langchain_core.prompts import ChatPromptTemplate
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是专业的量化研究分析师。基于技术面和基本面数据生成投研报告。
        
输出格式：
# {ticker} 投研报告

## 技术面分析
## 基本面评估
## 风险提示
## 综合建议（买入/持有/卖出，配置比例建议）

注意：这仅是量化分析参考，不构成投资建议。"""),
        ("human", "分析数据：{analysis_data}\n\n请生成投研报告。"),
    ])
    chain = prompt | _llm()  # Prompt | LLM 组成一条 Chain
    result = ""
    for chunk in chain.stream({"ticker": ticker, "analysis_data": str(analysis)}):
        result += chunk.content  # stream：逐 token 拼接，最终返回完整报告
    return result
