# tools/fundamental_metrics.py — 基本面指标计算
"""
计算股票基本面评估指标：
- P/E 估值
- EPS增速
- 营收增速
- ROE
- 债务比率
- 自由现金流
- 格雷厄姆数（Graham Number）
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FundamentalMetrics:
    ticker: str
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    eps: Optional[float] = None
    eps_growth: Optional[float] = None       # YoY %
    revenue_growth: Optional[float] = None   # YoY %
    roe: Optional[float] = None
    debt_to_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None   # 单位：百万
    graham_number: Optional[float] = None
    dividend_yield: Optional[float] = None
    valuation: str = "fair"                  # undervalued | fair | overvalued
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def compute_fundamental_metrics(
    ticker: str,
    price: float,
    eps: float,
    book_value_per_share: float,
    revenue_current: float,
    revenue_prev: float,
    eps_current: float,
    eps_prev: float,
    total_equity: float,
    net_income: float,
    total_debt: float,
    free_cash_flow: float,
    dividend_per_share: float = 0.0,
) -> FundamentalMetrics:
    """
    计算基本面指标。
    
    Args:
        price: 当前股价
        eps: 每股收益
        book_value_per_share: 每股净资产
        revenue_current/prev: 当前/上期营收（百万）
        eps_current/prev: 当期/上期EPS
        total_equity: 股东权益（百万）
        net_income: 净利润（百万）
        total_debt: 总债务（百万）
        free_cash_flow: 自由现金流（百万）
        dividend_per_share: 每股股息
    """
    flags = []
    metrics = FundamentalMetrics(ticker=ticker)

    # P/E
    if eps and eps > 0:
        metrics.pe_ratio = round(price / eps, 2)
        if metrics.pe_ratio > 30:
            flags.append(f"估值偏高：P/E={metrics.pe_ratio:.1f}（>30）")
        elif metrics.pe_ratio < 10:
            flags.append(f"估值偏低：P/E={metrics.pe_ratio:.1f}（<10，注意价值陷阱）")

    # P/B
    if book_value_per_share and book_value_per_share > 0:
        metrics.pb_ratio = round(price / book_value_per_share, 2)
        if metrics.pb_ratio < 1.0:
            flags.append(f"P/B={metrics.pb_ratio:.2f}：低于净资产，潜在价值股")

    # EPS
    metrics.eps = round(eps, 4)
    if eps_prev and eps_prev != 0:
        metrics.eps_growth = round((eps_current - eps_prev) / abs(eps_prev) * 100, 2)
        if metrics.eps_growth > 20:
            flags.append(f"EPS高速增长：+{metrics.eps_growth:.1f}%")
        elif metrics.eps_growth < -20:
            flags.append(f"EPS大幅下滑：{metrics.eps_growth:.1f}%，需关注")

    # 营收增速
    if revenue_prev and revenue_prev != 0:
        metrics.revenue_growth = round((revenue_current - revenue_prev) / abs(revenue_prev) * 100, 2)

    # ROE
    if total_equity and total_equity > 0:
        metrics.roe = round(net_income / total_equity * 100, 2)
        if metrics.roe > 15:
            flags.append(f"ROE={metrics.roe:.1f}%：优秀（>15%）")
        elif metrics.roe < 0:
            flags.append(f"ROE={metrics.roe:.1f}%：负值，公司亏损")

    # 债务比率
    if total_equity and total_equity > 0:
        metrics.debt_to_equity = round(total_debt / total_equity, 2)
        if metrics.debt_to_equity > 2:
            flags.append(f"D/E={metrics.debt_to_equity:.2f}：高杠杆风险")

    # 自由现金流
    metrics.free_cash_flow = round(free_cash_flow, 2)
    if free_cash_flow < 0:
        flags.append("自由现金流为负：注意资金链风险")

    # Graham Number: sqrt(22.5 * EPS * BVPS)
    if eps > 0 and book_value_per_share > 0:
        metrics.graham_number = round(math.sqrt(22.5 * eps * book_value_per_share), 2)
        if metrics.graham_number > 0:
            margin_of_safety = (metrics.graham_number - price) / metrics.graham_number * 100
            if margin_of_safety > 20:
                flags.append(f"格雷厄姆数 {metrics.graham_number:.2f}：股价有 {margin_of_safety:.0f}% 安全边际")
            elif margin_of_safety < -30:
                flags.append(f"格雷厄姆数 {metrics.graham_number:.2f}：股价高于内在价值 {-margin_of_safety:.0f}%")

    # 股息收益率
    if dividend_per_share > 0:
        metrics.dividend_yield = round(dividend_per_share / price * 100, 2)

    # 综合估值判断
    overvalued_signals = sum(1 for f in flags if "偏高" in f or "高杠杆" in f or "高于内在价值" in f)
    undervalued_signals = sum(1 for f in flags if "偏低" in f or "安全边际" in f or "低于净资产" in f)
    if overvalued_signals > undervalued_signals:
        metrics.valuation = "overvalued"
    elif undervalued_signals > overvalued_signals:
        metrics.valuation = "undervalued"
    else:
        metrics.valuation = "fair"

    metrics.flags = flags
    return metrics
