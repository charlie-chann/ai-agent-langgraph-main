# tools/compliance_tool.py — Financial compliance and risk checks
"""Rule-based compliance checker for portfolio and trade compliance."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from langchain_core.tools import tool
from loguru import logger

from config import (
    MAX_POSITION_WEIGHT,
    VOLATILITY_WARN_THRESHOLD,
    RISK_FREE_RATE,
)

# ── Watchlist (demo — in production, load from a datasource) ─────────────────
_ESG_EXCLUSION_LIST = {
    "tobacco": ["BTI", "MO", "PM", "IMBBY"],
    "weapons": ["LMT", "NOC", "RTX", "GD", "BA"],
    "gambling": ["MGM", "CZR", "WYNN", "LVS"],
    "fossil_fuel_pure_play": ["CVX", "XOM", "COP", "DVN", "HAL"],
}

# Merge for quick lookup
_ALL_ESG_FLAGGED: dict[str, str] = {}
for category, tickers in _ESG_EXCLUSION_LIST.items():
    for t in tickers:
        _ALL_ESG_FLAGGED[t] = category


# ── SEC-style circuit breakers (thresholds, not actual SEC rules) ─────────────
_SEC_RULES = {
    "max_single_position_pct": MAX_POSITION_WEIGHT * 100,
    "max_sector_concentration_pct": 40.0,
    "max_leverage_ratio": 2.0,
    "min_diversification": 5,   # minimum unique positions
}


@tool
def check_position_compliance(ticker: str, weight: float, volatility: float | None = None) -> str:
    """Check if a single stock position meets compliance thresholds.
    Args:
        ticker: stock ticker symbol (e.g. 'AAPL')
        weight: position weight as decimal (e.g. 0.15 for 15%)
        volatility: annualised volatility as decimal (e.g. 0.35 for 35%), optional
    Returns: compliance report for this position.
    """
    ticker = ticker.strip().upper()
    results = []
    violations = 0
    warnings = 0

    # Concentration check
    max_w = _SEC_RULES["max_single_position_pct"] / 100
    if weight > max_w:
        results.append(f"❌ VIOLATION: Position weight {weight*100:.1f}% exceeds {max_w*100:.0f}% limit")
        violations += 1
    elif weight > max_w * 0.80:
        results.append(f"⚠️ WARNING: Position at {weight*100:.1f}% is close to {max_w*100:.0f}% limit")
        warnings += 1
    else:
        results.append(f"✅ Concentration: {weight*100:.1f}% — within limits")

    # ESG check
    if ticker in _ALL_ESG_FLAGGED:
        cat = _ALL_ESG_FLAGGED[ticker]
        results.append(f"⚠️ ESG FLAG: {ticker} is in {cat} exclusion category (check mandate restrictions)")
        warnings += 1
    else:
        results.append(f"✅ ESG: {ticker} not on exclusion watchlist")

    # Volatility check
    if volatility is not None:
        if volatility > VOLATILITY_WARN_THRESHOLD:
            results.append(f"⚠️ HIGH VOLATILITY: Annualised vol {volatility*100:.1f}% exceeds {VOLATILITY_WARN_THRESHOLD*100:.0f}% threshold")
            warnings += 1
        else:
            results.append(f"✅ Volatility: {volatility*100:.1f}% within acceptable range")

    status = "❌ FAIL" if violations > 0 else ("⚠️ REVIEW" if warnings > 0 else "✅ PASS")
    report = {
        "ticker": ticker,
        "status": status,
        "violations": violations,
        "warnings": warnings,
        "checks": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logger.info(f"[compliance] {ticker} status={status}")
    return json.dumps(report, ensure_ascii=False, indent=2)


@tool
def screen_portfolio_compliance(portfolio_json: str) -> str:
    """Run full compliance screening on a portfolio.
    Input: JSON array of {ticker, weight, sector, volatility?} objects.
    Returns: comprehensive compliance report with all violations and warnings.
    """
    try:
        portfolio = json.loads(portfolio_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"

    if not isinstance(portfolio, list) or not portfolio:
        return "Error: expected non-empty JSON array"

    violations = []
    warnings = []
    passed = []

    total_w = sum(float(h.get("weight", 0)) for h in portfolio)
    sector_weights: dict[str, float] = {}

    for h in portfolio:
        ticker = str(h.get("ticker", "?")).upper()
        weight = float(h.get("weight", 0))
        sector = str(h.get("sector", "Unknown"))
        vol = h.get("volatility")

        sector_weights[sector] = sector_weights.get(sector, 0) + weight

        # Position size
        norm_w = weight / total_w if total_w else 0
        max_w = _SEC_RULES["max_single_position_pct"] / 100
        if norm_w > max_w:
            violations.append(f"❌ {ticker}: concentration {norm_w*100:.1f}% > {max_w*100:.0f}%")
        elif norm_w > max_w * 0.80:
            warnings.append(f"⚠️ {ticker}: concentration {norm_w*100:.1f}% near {max_w*100:.0f}% limit")
        else:
            passed.append(f"✅ {ticker}: {norm_w*100:.1f}%")

        # ESG
        if ticker in _ALL_ESG_FLAGGED:
            warnings.append(f"⚠️ {ticker}: ESG flag — {_ALL_ESG_FLAGGED[ticker]}")

        # Volatility
        if vol is not None:
            fv = float(vol)
            if fv > VOLATILITY_WARN_THRESHOLD:
                warnings.append(f"⚠️ {ticker}: high volatility {fv*100:.1f}%")

    # Sector concentration
    for sector, sw in sector_weights.items():
        norm = sw / total_w if total_w else 0
        if norm > _SEC_RULES["max_sector_concentration_pct"] / 100:
            violations.append(f"❌ Sector {sector}: {norm*100:.1f}% > {_SEC_RULES['max_sector_concentration_pct']:.0f}%")

    # Diversification
    if len(portfolio) < _SEC_RULES["min_diversification"]:
        warnings.append(f"⚠️ Only {len(portfolio)} positions — consider diversifying (min {_SEC_RULES['min_diversification']} recommended)")

    overall = "❌ NON-COMPLIANT" if violations else ("⚠️ NEEDS REVIEW" if warnings else "✅ COMPLIANT")
    return json.dumps({
        "overall_status": overall,
        "violations": violations,
        "warnings": warnings,
        "passed_checks": passed,
        "positions_screened": len(portfolio),
        "rules_applied": _SEC_RULES,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2)


@tool
def get_compliance_rules() -> str:
    """Return the current compliance rules and thresholds in use.
    Returns: JSON describing all active compliance thresholds.
    """
    return json.dumps({
        "position_limits": {
            "max_single_position_pct": _SEC_RULES["max_single_position_pct"],
            "max_sector_concentration_pct": _SEC_RULES["max_sector_concentration_pct"],
            "min_positions_for_diversification": _SEC_RULES["min_diversification"],
        },
        "risk_thresholds": {
            "volatility_warning_threshold_pct": VOLATILITY_WARN_THRESHOLD * 100,
            "risk_free_rate_pct": RISK_FREE_RATE * 100,
        },
        "esg_exclusion_categories": list(_ESG_EXCLUSION_LIST.keys()),
        "note": "These are demonstration thresholds. Configure via .env or config.py for production use.",
    }, ensure_ascii=False, indent=2)
