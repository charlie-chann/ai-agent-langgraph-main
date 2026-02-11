# tools/market_data.py — Real market data via yfinance
"""Fetch live stock prices, fundamentals, and historical data using yfinance."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from langchain_core.tools import tool
from loguru import logger

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

from config import PRICE_HISTORY_PERIOD


def _yf_required(fn):
    """Decorator to return helpful error if yfinance not installed."""
    def wrapper(*args, **kwargs):
        if not _YF_AVAILABLE:
            return "yfinance not installed. Run: pip install yfinance"
        return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _safe_val(val: Any) -> Any:
    """Convert NaN / None to None for JSON safety."""
    if val is None:
        return None
    try:
        import math
        if math.isnan(float(val)):
            return None
        return round(float(val), 4)
    except (TypeError, ValueError):
        return val


@tool
def get_stock_quote(ticker: str) -> str:
    """Get the current stock quote and key metrics for a ticker symbol.
    Input: ticker symbol (e.g. 'AAPL', 'TSLA', 'MSFT').
    Returns: current price, change, volume, market cap, PE ratio, etc.
    """
    if not _YF_AVAILABLE:
        return "yfinance not installed"
    ticker = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker)
        info = t.info
        price = _safe_val(info.get("currentPrice") or info.get("regularMarketPrice"))
        prev_close = _safe_val(info.get("previousClose") or info.get("regularMarketPreviousClose"))
        change_pct = None
        if price and prev_close and prev_close != 0:
            change_pct = round((price - prev_close) / prev_close * 100, 2)

        result = {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "price": price,
            "prev_close": prev_close,
            "change_pct": change_pct,
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": _safe_val(info.get("trailingPE")),
            "forward_pe": _safe_val(info.get("forwardPE")),
            "pb_ratio": _safe_val(info.get("priceToBook")),
            "ps_ratio": _safe_val(info.get("priceToSalesTrailing12Months")),
            "dividend_yield": _safe_val(info.get("dividendYield")),
            "beta": _safe_val(info.get("beta")),
            "52w_high": _safe_val(info.get("fiftyTwoWeekHigh")),
            "52w_low": _safe_val(info.get("fiftyTwoWeekLow")),
            "analyst_target": _safe_val(info.get("targetMeanPrice")),
            "recommendation": info.get("recommendationKey", "N/A"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[market_data] quote {ticker} price={price}")
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[market_data] {ticker}: {e}")
        return f"Error fetching {ticker}: {e}"


@tool
def get_financials(ticker: str) -> str:
    """Get income statement, balance sheet, and cash flow highlights for a stock.
    Input: ticker symbol (e.g. 'AAPL').
    Returns: key financial metrics from the most recent annual report.
    """
    if not _YF_AVAILABLE:
        return "yfinance not installed"
    ticker = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker)
        info = t.info

        result = {
            "ticker": ticker,
            # Income statement
            "revenue_ttm": info.get("totalRevenue"),
            "gross_margin": _safe_val(info.get("grossMargins")),
            "operating_margin": _safe_val(info.get("operatingMargins")),
            "net_margin": _safe_val(info.get("profitMargins")),
            "revenue_growth": _safe_val(info.get("revenueGrowth")),
            "earnings_growth": _safe_val(info.get("earningsGrowth")),
            "eps": _safe_val(info.get("trailingEps")),
            "eps_forward": _safe_val(info.get("forwardEps")),
            # Balance sheet
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "debt_to_equity": _safe_val(info.get("debtToEquity")),
            "current_ratio": _safe_val(info.get("currentRatio")),
            "quick_ratio": _safe_val(info.get("quickRatio")),
            "book_value_per_share": _safe_val(info.get("bookValue")),
            # Returns
            "return_on_equity": _safe_val(info.get("returnOnEquity")),
            "return_on_assets": _safe_val(info.get("returnOnAssets")),
            # Cash flow
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
        }
        logger.info(f"[market_data] financials {ticker}")
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching financials for {ticker}: {e}"


@tool
def get_price_history(ticker: str, period: str = "") -> str:
    """Get historical price data for technical analysis.
    Input: ticker symbol, optionally period ('1mo', '3mo', '6mo', '1y', '2y').
    Returns: OHLCV summary with moving averages and volatility.
    """
    if not _YF_AVAILABLE:
        return "yfinance not installed"
    ticker = ticker.strip().upper()
    period = period.strip() or PRICE_HISTORY_PERIOD
    valid_periods = {"1mo", "3mo", "6mo", "1y", "2y", "5y"}
    if period not in valid_periods:
        period = "1y"
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if hist.empty:
            return f"No price history found for {ticker}"

        close = hist["Close"]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

        # Annualised volatility
        daily_returns = close.pct_change().dropna()
        volatility = float(daily_returns.std() * (252 ** 0.5)) if len(daily_returns) > 1 else None

        result = {
            "ticker": ticker,
            "period": period,
            "current_price": _safe_val(close.iloc[-1]),
            "period_start_price": _safe_val(close.iloc[0]),
            "period_return_pct": _safe_val((close.iloc[-1] / close.iloc[0] - 1) * 100),
            "period_high": _safe_val(hist["High"].max()),
            "period_low": _safe_val(hist["Low"].min()),
            "avg_daily_volume": _safe_val(hist["Volume"].mean()),
            "ma_20": _safe_val(ma20),
            "ma_50": _safe_val(ma50),
            "ma_200": _safe_val(ma200),
            "annualised_volatility": _safe_val(volatility),
            "trend": "bullish" if close.iloc[-1] > ma50 else "bearish",
            "data_points": len(hist),
        }
        logger.info(f"[market_data] history {ticker} period={period}")
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching price history for {ticker}: {e}"


@tool
def compare_stocks(tickers: str) -> str:
    """Compare multiple stocks side by side on key metrics.
    Input: comma-separated ticker symbols (e.g. 'AAPL,MSFT,GOOGL').
    Returns: comparison table of key financial metrics.
    """
    if not _YF_AVAILABLE:
        return "yfinance not installed"
    symbols = [t.strip().upper() for t in tickers.split(",") if t.strip()][:5]
    if not symbols:
        return "No valid tickers provided"

    rows = []
    for sym in symbols:
        try:
            info = yf.Ticker(sym).info
            rows.append({
                "ticker": sym,
                "name": (info.get("shortName") or sym)[:20],
                "sector": info.get("sector", "N/A"),
                "market_cap_B": _safe_val((info.get("marketCap") or 0) / 1e9),
                "pe": _safe_val(info.get("trailingPE")),
                "pb": _safe_val(info.get("priceToBook")),
                "net_margin": _safe_val(info.get("profitMargins")),
                "roe": _safe_val(info.get("returnOnEquity")),
                "revenue_growth": _safe_val(info.get("revenueGrowth")),
                "beta": _safe_val(info.get("beta")),
                "div_yield": _safe_val(info.get("dividendYield")),
                "recommendation": info.get("recommendationKey", "N/A"),
            })
        except Exception as e:
            rows.append({"ticker": sym, "error": str(e)})

    return json.dumps(rows, ensure_ascii=False, indent=2)
