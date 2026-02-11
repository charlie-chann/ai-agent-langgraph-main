# tools/analysis_tool.py — Fundamental & technical analysis calculations
"""Pure-Python financial calculations — no external API needed."""
from __future__ import annotations

import json
import math
from langchain_core.tools import tool
from loguru import logger

from config import RISK_FREE_RATE


def _pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val * 100:.1f}%"


def _fmt(val: float | None, decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{decimals}f}"


@tool
def calculate_dcf(
    free_cash_flow: float,
    growth_rate: float,
    terminal_growth_rate: float,
    discount_rate: float,
    years: int = 5,
) -> str:
    """Calculate Discounted Cash Flow (DCF) intrinsic value.
    Args:
        free_cash_flow: current annual FCF in dollars (e.g. 5000000000 for $5B)
        growth_rate: expected FCF growth rate for projection period (e.g. 0.10 for 10%)
        terminal_growth_rate: long-term perpetual growth rate (e.g. 0.03 for 3%)
        discount_rate: WACC or required rate of return (e.g. 0.10 for 10%)
        years: projection period in years (default 5)
    Returns: DCF valuation details.
    """
    if discount_rate <= terminal_growth_rate:
        return "Error: discount_rate must be greater than terminal_growth_rate"
    if not (0 < years <= 20):
        return "Error: years must be between 1 and 20"

    try:
        # Project FCF
        projected = []
        cf = free_cash_flow
        for yr in range(1, years + 1):
            cf = cf * (1 + growth_rate)
            pv = cf / ((1 + discount_rate) ** yr)
            projected.append({"year": yr, "fcf": round(cf, 0), "pv": round(pv, 0)})

        # Terminal value
        terminal_fcf = projected[-1]["fcf"] * (1 + terminal_growth_rate)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth_rate)
        pv_terminal = terminal_value / ((1 + discount_rate) ** years)

        sum_pv = sum(p["pv"] for p in projected)
        total_value = sum_pv + pv_terminal

        result = {
            "inputs": {
                "free_cash_flow": free_cash_flow,
                "growth_rate": _pct(growth_rate),
                "terminal_growth_rate": _pct(terminal_growth_rate),
                "discount_rate": _pct(discount_rate),
                "projection_years": years,
            },
            "projected_cash_flows": projected,
            "pv_of_projected_fcf": round(sum_pv, 0),
            "terminal_value": round(terminal_value, 0),
            "pv_of_terminal_value": round(pv_terminal, 0),
            "total_intrinsic_value": round(total_value, 0),
            "note": "Divide by shares outstanding for per-share intrinsic value",
        }
        logger.info(f"[analysis] DCF total_value={total_value:.0f}")
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"DCF calculation error: {e}"


@tool
def analyse_fundamentals(metrics_json: str) -> str:
    """Analyse a set of financial metrics and produce a quality score.
    Input: JSON string with keys: pe, pb, roe, net_margin, debt_to_equity,
           current_ratio, revenue_growth, earnings_growth, beta.
    Returns: structured analysis with scores and commentary.
    """
    try:
        m = json.loads(metrics_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON input: {e}"

    def safe(key: str) -> float | None:
        val = m.get(key)
        if val is None:
            return None
        try:
            f = float(val)
            return None if math.isnan(f) else f
        except (TypeError, ValueError):
            return None

    checks = []
    score = 0
    max_score = 0

    def check(label: str, passed: bool | None, good: str, bad: str, weight: int = 1):
        nonlocal score, max_score
        max_score += weight
        if passed is True:
            score += weight
            checks.append(f"✅ {label}: {good}")
        elif passed is False:
            checks.append(f"❌ {label}: {bad}")
        else:
            checks.append(f"⚪ {label}: data not available")

    pe = safe("pe")
    check("Valuation (P/E)",
          None if pe is None else 0 < pe < 30,
          f"P/E={_fmt(pe)} — reasonable valuation",
          f"P/E={_fmt(pe)} — potentially {'overvalued' if pe and pe > 30 else 'negative earnings'}")

    pb = safe("pb")
    check("Price/Book",
          None if pb is None else pb < 4,
          f"P/B={_fmt(pb)} — acceptable",
          f"P/B={_fmt(pb)} — premium multiple, justify with high ROE")

    roe = safe("roe")
    check("Return on Equity",
          None if roe is None else roe > 0.12,
          f"ROE={_pct(roe)} — strong shareholder returns",
          f"ROE={_pct(roe)} — below 12% threshold")

    nm = safe("net_margin")
    check("Net Margin",
          None if nm is None else nm > 0.05,
          f"Net margin={_pct(nm)}",
          f"Net margin={_pct(nm)} — thin margins, cost pressure risk")

    de = safe("debt_to_equity")
    check("Debt/Equity",
          None if de is None else de < 200,
          f"D/E={_fmt(de)} — manageable leverage",
          f"D/E={_fmt(de)} — high leverage, monitor interest coverage", weight=2)

    cr = safe("current_ratio")
    check("Current Ratio",
          None if cr is None else cr > 1.0,
          f"Current ratio={_fmt(cr)} — adequate liquidity",
          f"Current ratio={_fmt(cr)} — below 1.0, short-term liquidity risk", weight=2)

    rg = safe("revenue_growth")
    check("Revenue Growth",
          None if rg is None else rg > 0.05,
          f"Revenue growth={_pct(rg)} — expanding business",
          f"Revenue growth={_pct(rg)} — stagnant / declining revenue")

    eg = safe("earnings_growth")
    check("Earnings Growth",
          None if eg is None else eg > 0.0,
          f"Earnings growth={_pct(eg)} — improving profitability",
          f"Earnings growth={_pct(eg)} — earnings declining")

    beta = safe("beta")
    risk = "Low" if beta and beta < 0.8 else ("High" if beta and beta > 1.5 else "Moderate")
    checks.append(f"📊 Beta={_fmt(beta)} — {risk} market sensitivity")

    pct_score = round(score / max_score * 100) if max_score else 0
    rating = "Strong Buy" if pct_score >= 75 else ("Buy" if pct_score >= 60 else ("Hold" if pct_score >= 40 else "Sell"))

    return json.dumps({
        "score": f"{score}/{max_score} ({pct_score}%)",
        "overall_rating": rating,
        "analysis": checks,
    }, ensure_ascii=False, indent=2)


@tool
def calculate_portfolio_metrics(holdings_json: str) -> str:
    """Calculate portfolio diversification and risk metrics.
    Input: JSON array of {ticker, weight, beta, sector} objects.
         weights should sum to 1.0 (e.g. [{"ticker":"AAPL","weight":0.15,"beta":1.2,"sector":"Technology"},...])
    Returns: portfolio-level metrics.
    """
    try:
        holdings = json.loads(holdings_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if not isinstance(holdings, list) or len(holdings) == 0:
        return "Error: expected a non-empty JSON array"

    total_weight = sum(float(h.get("weight", 0)) for h in holdings)
    portfolio_beta = 0.0
    sector_weights: dict[str, float] = {}
    max_weight = 0.0
    max_ticker = ""

    for h in holdings:
        w = float(h.get("weight", 0))
        beta = float(h.get("beta", 1.0) or 1.0)
        sector = str(h.get("sector", "Unknown"))
        ticker = str(h.get("ticker", "?"))

        portfolio_beta += w * beta
        sector_weights[sector] = sector_weights.get(sector, 0) + w
        if w > max_weight:
            max_weight = w
            max_ticker = ticker

    result = {
        "total_weight": round(total_weight, 4),
        "num_positions": len(holdings),
        "portfolio_beta": round(portfolio_beta / total_weight, 3) if total_weight else None,
        "sector_allocation": {k: f"{v / total_weight * 100:.1f}%" for k, v in sorted(sector_weights.items())},
        "largest_position": {"ticker": max_ticker, "weight": f"{max_weight / total_weight * 100:.1f}%"},
        "diversification_score": min(10, len(holdings) // 2),
        "warnings": [],
    }

    if max_weight / total_weight > 0.20:
        result["warnings"].append(f"⚠️ {max_ticker} exceeds 20% concentration limit ({max_weight/total_weight*100:.1f}%)")
    if total_weight < 0.99 or total_weight > 1.01:
        result["warnings"].append(f"⚠️ Weights sum to {total_weight:.4f} (should be 1.0)")
    for sector, sw in sector_weights.items():
        if sw / total_weight > 0.40:
            result["warnings"].append(f"⚠️ {sector} sector overweight ({sw/total_weight*100:.1f}%)")

    return json.dumps(result, ensure_ascii=False, indent=2)
