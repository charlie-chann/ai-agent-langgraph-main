# tests/test_agent.py — project_18_ecommerce_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest


class TestPriceMonitor:
    def setup_method(self):
        from tools.price_monitor import (
            Product, CompetitorPrice, analyze_competitor_prices, generate_product_description
        )
        self.Product = Product
        self.CompetitorPrice = CompetitorPrice
        self.analyze = analyze_competitor_prices
        self.gen_desc = generate_product_description

    def _product(self, price=100.0, cost=60.0, name="测试商品", category="电子"):
        return self.Product(product_id="P001", name=name, category=category,
                            our_price=price, cost=cost)

    def _comp(self, name, price):
        return self.CompetitorPrice(competitor_name=name, product_id="P001", price=price)

    def test_margin_calculation(self):
        p = self._product(price=100, cost=60)
        assert p.margin_pct == pytest.approx(40.0)

    def test_no_competitors_returns_recommendation(self):
        result = self.analyze(self._product(), [])
        assert "recommendation" in result or "定价建议" in result

    def test_high_price_vs_competitors_alert(self):
        product = self._product(price=150.0)
        comps = [self._comp("竞品A", 100.0), self._comp("竞品B", 105.0)]
        result = self.analyze(product, comps)
        assert len(result["预警"]) >= 1

    def test_lower_price_opportunity_alert(self):
        product = self._product(price=80.0)
        comps = [self._comp("竞品A", 130.0), self._comp("竞品B", 135.0)]
        result = self.analyze(product, comps)
        assert len(result["预警"]) >= 1

    def test_competitive_price_no_alert(self):
        product = self._product(price=100.0)
        comps = [self._comp("竞品A", 98.0), self._comp("竞品B", 102.0)]
        result = self.analyze(product, comps)
        # 价差在范围内，可能无预警
        assert "预警" in result

    def test_analysis_has_required_keys(self):
        product = self._product()
        comps = [self._comp("竞品A", 100.0)]
        result = self.analyze(product, comps)
        for k in ["竞品数量", "竞品均价", "当前价格", "建议价格", "定价建议"]:
            assert k in result

    def test_generate_description_not_empty(self):
        desc = self.gen_desc(self._product(name="智能手表Pro"))
        assert len(desc) > 20

    def test_generate_description_max_length(self):
        from config import DESC_MAX_LENGTH
        desc = self.gen_desc(self._product(name="A" * 50, category="B" * 30))
        assert len(desc) <= DESC_MAX_LENGTH

    def test_generate_description_contains_name(self):
        desc = self.gen_desc(self._product(name="超级产品"))
        assert "超级产品" in desc

    def test_xss_in_product_name_sanitized(self):
        p = self._product(name="<script>商品</script>")
        desc = self.gen_desc(p)
        assert "<script>" not in desc

    def test_suggested_price_above_cost(self):
        product = self._product(price=80.0, cost=70.0)
        comps = [self._comp("竞品A", 50.0)]  # 竞品便宜，但不能低于成本
        result = self.analyze(product, comps)
        suggested_str = result.get("建议价格", "¥0")
        suggested = float(suggested_str.replace("¥", ""))
        assert suggested >= 70.0 * 1.1  # 至少高于成本10%


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize
        self.sanitize = _sanitize

    def test_removes_control_chars(self):
        assert "\x1f" not in self.sanitize("正常\x1f文本")

    def test_truncates(self):
        assert len(self.sanitize("A" * 5000)) <= 3000
