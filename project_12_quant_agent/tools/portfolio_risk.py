# tools/portfolio_risk.py — 投资组合风险计算
"""
计算投资组合风险指标：
- 夏普比率（Sharpe Ratio）
- 最大回撤（Max Drawdown）
- 波动率（Volatility）
- Beta（相对标普500）
- VaR（风险价值）
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from config import RISK_FREE_RATE


@dataclass
class PortfolioRisk:
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None      # 百分比，负值
    annual_volatility: Optional[float] = None # 年化波动率
    annual_return: Optional[float] = None     # 年化收益率
    var_95: Optional[float] = None            # 95% VaR (daily)
    beta: Optional[float] = None
    risk_level: str = "medium"                # low | medium | high
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def compute_portfolio_risk(
    returns: list[float],            # 日收益率序列
    benchmark_returns: list[float] | None = None,
    trading_days: int = 252,
) -> PortfolioRisk:
    """
    计算组合风险指标。
    
    Args:
        returns: 日收益率列表（如 [0.01, -0.02, 0.005, ...]）
        benchmark_returns: 基准（如标普500）日收益率
        trading_days: 年化基数
    """
    if len(returns) < 10:
        return PortfolioRisk()

    warnings = []
    n = len(returns)

    # 年化收益率
    mean_daily = sum(returns) / n
    annual_return = mean_daily * trading_days

    # 年化波动率
    variance = sum((r - mean_daily) ** 2 for r in returns) / (n - 1)
    daily_std = variance ** 0.5
    annual_vol = daily_std * (trading_days ** 0.5)

    # 夏普比率
    daily_rf = RISK_FREE_RATE / trading_days
    excess_return = mean_daily - daily_rf
    sharpe = (excess_return / daily_std * (trading_days ** 0.5)) if daily_std > 0 else 0.0

    # 最大回撤
    cumulative = [1.0]
    for r in returns:
        cumulative.append(cumulative[-1] * (1 + r))
    peak = cumulative[0]
    max_dd = 0.0
    for v in cumulative:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd

    # 95% VaR（历史法）
    sorted_returns = sorted(returns)
    var_idx = int(0.05 * n)
    var_95 = sorted_returns[max(var_idx, 0)]

    # Beta（如果有基准收益率）
    beta = None
    if benchmark_returns and len(benchmark_returns) >= len(returns):
        bmk = benchmark_returns[-n:]
        cov_sum = sum((r - mean_daily) * (b - sum(bmk)/len(bmk)) for r, b in zip(returns, bmk))
        bm_var = sum((b - sum(bmk)/len(bmk)) ** 2 for b in bmk)
        if bm_var > 0:
            beta = round(cov_sum / bm_var, 3)

    # 风险评级
    if annual_vol > 0.30 or max_dd < -0.30:
        risk_level = "high"
        warnings.append(f"年化波动率={annual_vol:.1%}，风险较高")
    elif annual_vol > 0.15 or max_dd < -0.15:
        risk_level = "medium"
    else:
        risk_level = "low"

    if sharpe < 0:
        warnings.append("夏普比率为负，风险调整后收益不理想")

    return PortfolioRisk(
        sharpe_ratio=round(sharpe, 4),
        max_drawdown=round(max_dd, 4),
        annual_volatility=round(annual_vol, 4),
        annual_return=round(annual_return, 4),
        var_95=round(var_95, 4),
        beta=beta,
        risk_level=risk_level,
        warnings=warnings,
    )
