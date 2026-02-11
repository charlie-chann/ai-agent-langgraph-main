# tests/test_agent.py — project_12_quant_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import math


# ── Technical Indicators Tests ────────────────────────────────────────────────
class TestTechnicalIndicators:
    def setup_method(self):
        from tools.technical_indicators import compute_signals, _sma, _ema, _rsi
        self.compute = compute_signals
        self.sma = _sma
        self.ema = _ema
        self.rsi = _rsi

    def _mock_prices(self, n: int = 60, start: float = 100.0, trend: float = 0.5) -> list[float]:
        """Generate mock trending prices."""
        prices = [start]
        for i in range(1, n):
            prices.append(round(prices[-1] + trend + (i % 3 - 1) * 0.3, 2))
        return prices

    def test_sma_correct_value(self):
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert self.sma(prices, 3) == pytest.approx(4.0)

    def test_sma_insufficient_data(self):
        assert self.sma([1.0, 2.0], 5) is None

    def test_ema_reasonable_range(self):
        prices = self._mock_prices(30)
        ema = self.ema(prices, 12)
        assert ema is not None
        # EMA should be close to recent prices
        assert prices[-1] * 0.5 < ema < prices[-1] * 1.5

    def test_rsi_oversold_signal(self):
        # Declining prices should give low RSI
        prices = [100.0 - i * 2 for i in range(20)]
        rsi = self.rsi(prices, 14)
        assert rsi is not None
        assert rsi < 40  # Should show oversold/downtrend

    def test_rsi_overbought_signal(self):
        # Rising prices should give high RSI
        prices = [100.0 + i * 2 for i in range(20)]
        rsi = self.rsi(prices, 14)
        assert rsi is not None
        assert rsi > 60

    def test_compute_signals_returns_result(self):
        prices = self._mock_prices(60)
        result = self.compute("AAPL", prices)
        assert result.ticker == "AAPL"
        assert result.close_price == prices[-1]

    def test_compute_signals_has_sma(self):
        prices = self._mock_prices(60)
        result = self.compute("AAPL", prices)
        assert result.sma_20 is not None
        assert result.sma_50 is not None

    def test_compute_signals_bullish_trend(self):
        # Strongly uptrending prices
        prices = [50.0 + i * 1.0 for i in range(60)]
        result = self.compute("TEST", prices)
        assert result.trend in ("bullish", "neutral")

    def test_compute_signals_bearish_trend(self):
        # Strongly downtrending prices
        prices = [150.0 - i * 1.0 for i in range(60)]
        result = self.compute("TEST", prices)
        assert result.trend in ("bearish", "neutral")

    def test_to_dict_has_required_keys(self):
        prices = self._mock_prices(60)
        result = self.compute("AAPL", prices)
        d = result.to_dict()
        for key in ["ticker", "close_price", "rsi_14", "trend", "signals"]:
            assert key in d


# ── Fundamental Metrics Tests ──────────────────────────────────────────────────
class TestFundamentalMetrics:
    def setup_method(self):
        from tools.fundamental_metrics import compute_fundamental_metrics
        self.compute = compute_fundamental_metrics

    def _base_kwargs(self, **overrides):
        base = dict(
            ticker="TEST",
            price=100.0,
            eps=5.0,
            book_value_per_share=40.0,
            revenue_current=500.0,
            revenue_prev=400.0,
            eps_current=5.0,
            eps_prev=4.0,
            total_equity=1000.0,
            net_income=200.0,
            total_debt=300.0,
            free_cash_flow=80.0,
        )
        base.update(overrides)
        return base

    def test_pe_ratio_computed(self):
        m = self.compute(**self._base_kwargs(price=100.0, eps=5.0))
        assert m.pe_ratio == pytest.approx(20.0)

    def test_pb_ratio_computed(self):
        m = self.compute(**self._base_kwargs(price=100.0, book_value_per_share=50.0))
        assert m.pb_ratio == pytest.approx(2.0)

    def test_roe_computed(self):
        m = self.compute(**self._base_kwargs(net_income=200.0, total_equity=1000.0))
        assert m.roe == pytest.approx(20.0)

    def test_high_pe_flagged_overvalued(self):
        m = self.compute(**self._base_kwargs(price=350.0, eps=5.0))
        assert m.pe_ratio > 30
        assert any("偏高" in f for f in m.flags)

    def test_negative_fcf_flagged(self):
        m = self.compute(**self._base_kwargs(free_cash_flow=-50.0))
        assert any("现金流为负" in f for f in m.flags)

    def test_graham_number_computed(self):
        # Graham = sqrt(22.5 * eps * bvps)
        m = self.compute(**self._base_kwargs(eps=5.0, book_value_per_share=40.0))
        expected = math.sqrt(22.5 * 5.0 * 40.0)
        assert m.graham_number == pytest.approx(expected, abs=0.1)

    def test_high_revenue_growth_positive(self):
        m = self.compute(**self._base_kwargs(revenue_current=600.0, revenue_prev=400.0))
        assert m.revenue_growth == pytest.approx(50.0)

    def test_to_dict_structure(self):
        m = self.compute(**self._base_kwargs())
        d = m.to_dict()
        assert "ticker" in d
        assert "pe_ratio" in d
        assert "valuation" in d


# ── Portfolio Risk Tests ───────────────────────────────────────────────────────
class TestPortfolioRisk:
    def setup_method(self):
        from tools.portfolio_risk import compute_portfolio_risk
        self.compute = compute_portfolio_risk

    def test_high_volatility_rated_high_risk(self):
        # Returns with high volatility (±10% per day)
        import random
        random.seed(42)
        returns = [random.gauss(0.001, 0.10) for _ in range(252)]
        risk = self.compute(returns)
        assert risk.risk_level == "high"

    def test_stable_returns_low_risk(self):
        # Low volatility returns (~0.5%/day)
        returns = [0.002] * 100
        risk = self.compute(returns)
        assert risk.risk_level == "low"
        assert risk.max_drawdown == pytest.approx(0.0, abs=0.01)

    def test_negative_returns_negative_sharpe(self):
        # Use realistic noisy negative returns to avoid zero-volatility edge case
        import random
        random.seed(7)
        returns = [-0.005 + random.gauss(0, 0.002) for _ in range(100)]
        risk = self.compute(returns)
        assert risk.sharpe_ratio is not None
        assert risk.sharpe_ratio < 0

    def test_max_drawdown_calculated(self):
        # Price goes up then crashes
        returns = [0.05] * 10 + [-0.10] * 10
        risk = self.compute(returns)
        assert risk.max_drawdown < 0

    def test_sharpe_ratio_computed(self):
        # Use realistic noisy positive returns to avoid zero-volatility edge case
        import random
        random.seed(13)
        returns = [0.003 + random.gauss(0, 0.001) for _ in range(200)]
        risk = self.compute(returns)
        assert risk.sharpe_ratio is not None
        assert risk.sharpe_ratio > 0

    def test_insufficient_data_returns_empty(self):
        risk = self.compute([0.01, 0.02])  # Less than 10
        assert risk.sharpe_ratio is None

    def test_beta_computed_with_benchmark(self):
        benchmark = [0.001 + 0.0005 * i % 3 for i in range(100)]
        returns = [b * 1.2 for b in benchmark]  # Beta ~ 1.2
        risk = self.compute(returns, benchmark_returns=benchmark)
        assert risk.beta is not None


# ── Ticker Sanitization Tests ──────────────────────────────────────────────────
class TestTickerSanitization:
    def setup_method(self):
        from agent import _sanitize_ticker
        self.sanitize = _sanitize_ticker

    def test_valid_ticker_uppercase(self):
        assert self.sanitize("aapl") == "AAPL"

    def test_valid_ticker_with_dot(self):
        assert self.sanitize("BRK.A") == "BRK.A"

    def test_empty_ticker_raises(self):
        with pytest.raises(ValueError, match="不能为空"):
            self.sanitize("")

    def test_invalid_ticker_raises(self):
        with pytest.raises(ValueError, match="无效"):
            self.sanitize("AAPL; DROP TABLE")
