# tools/technical_indicators.py — 技术指标计算（纯Python，不依赖 TA-Lib）
"""
实现常用技术指标：
- SMA (简单移动平均)
- EMA (指数移动平均)
- RSI (相对强弱指数)
- MACD (移动平均收敛散度)
- Bollinger Bands (布林带)
- ATR (真实波幅)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TechnicalSignals:
    ticker: str
    close_price: float
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    atr_14: Optional[float] = None
    trend: str = "neutral"          # bullish | bearish | neutral
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in self.__dict__.items()}


def _sma(prices: list[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _ema(prices: list[float], period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period  # seed with SMA
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def _rsi(prices: list[float], period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [c for c in changes if c > 0]
    losses = [-c for c in changes if c < 0]
    avg_gain = sum(gains[-period:]) / period if gains else 0
    avg_loss = sum(losses[-period:]) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _bollinger_bands(prices: list[float], period: int = 20, std_mult: float = 2.0):
    if len(prices) < period:
        return None, None, None
    window = prices[-period:]
    mid = sum(window) / period
    variance = sum((p - mid) ** 2 for p in window) / period
    std = variance ** 0.5
    return mid + std_mult * std, mid, mid - std_mult * std


def _atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return sum(trs[-period:]) / period


def compute_signals(
    ticker: str,
    closes: list[float],
    highs: list[float] | None = None,
    lows: list[float] | None = None,
) -> TechnicalSignals:
    """计算全套技术指标并生成信号。"""
    if not closes or len(closes) < 2:
        return TechnicalSignals(ticker=ticker, close_price=0.0)

    price = closes[-1]
    signals_list = []

    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    rsi = _rsi(closes, 14)
    bb_upper, bb_mid, bb_lower = _bollinger_bands(closes, 20)
    macd = (ema12 - ema26) if (ema12 and ema26) else None
    atr = None
    if highs and lows:
        atr = _atr(highs, lows, closes, 14)

    # 生成信号
    if sma20 and sma50:
        if sma20 > sma50:
            signals_list.append("金叉：SMA20 上穿 SMA50（看涨）")
        else:
            signals_list.append("死叉：SMA20 下穿 SMA50（看跌）")

    if rsi is not None:
        if rsi < 30:
            signals_list.append(f"RSI={rsi:.1f}：超卖区间（潜在反弹机会）")
        elif rsi > 70:
            signals_list.append(f"RSI={rsi:.1f}：超买区间（注意回调风险）")

    if macd is not None:
        if macd > 0:
            signals_list.append(f"MACD={macd:.3f}：正值，动能向上")
        else:
            signals_list.append(f"MACD={macd:.3f}：负值，动能向下")

    if bb_lower and price < bb_lower:
        signals_list.append("价格跌破布林下轨（超卖信号）")
    elif bb_upper and price > bb_upper:
        signals_list.append("价格突破布林上轨（超买信号）")

    # 综合趋势判断
    bullish_count = sum(1 for s in signals_list if "看涨" in s or "反弹" in s or "上穿" in s or "向上" in s)
    bearish_count = sum(1 for s in signals_list if "看跌" in s or "回调" in s or "下穿" in s or "向下" in s)
    if bullish_count > bearish_count:
        trend = "bullish"
    elif bearish_count > bullish_count:
        trend = "bearish"
    else:
        trend = "neutral"

    return TechnicalSignals(
        ticker=ticker,
        close_price=price,
        sma_20=sma20,
        sma_50=sma50,
        ema_12=ema12,
        ema_26=ema26,
        rsi_14=rsi,
        macd=macd,
        macd_signal=None,
        bb_upper=bb_upper,
        bb_middle=bb_mid,
        bb_lower=bb_lower,
        atr_14=atr,
        trend=trend,
        signals=signals_list,
    )
