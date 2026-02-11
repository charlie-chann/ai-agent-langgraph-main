# tests/test_agent.py — project_15_supply_chain_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import math


class TestInventoryTool:
    def setup_method(self):
        from tools.inventory_tool import InventoryItem, analyze_inventory, forecast_demand
        self.InventoryItem = InventoryItem
        self.analyze = analyze_inventory
        self.forecast = forecast_demand

    def _item(self, sku="SKU001", stock=100, demand=10.0, cost=5.0, lead=3):
        return self.InventoryItem(sku=sku, name="测试商品", current_stock=stock,
                                  daily_demand=demand, unit_cost=cost, lead_time_days=lead)

    def test_days_of_stock_calculation(self):
        item = self._item(stock=100, demand=10.0)
        assert item.days_of_stock == pytest.approx(10.0)

    def test_status_critical(self):
        item = self._item(stock=20, demand=10.0)  # 2 days → critical
        assert item.status == "critical"

    def test_status_low(self):
        item = self._item(stock=50, demand=10.0)  # 5 days → low
        assert item.status == "low"

    def test_status_normal(self):
        item = self._item(stock=200, demand=10.0)  # 20 days → normal
        assert item.status == "normal"

    def test_analyze_generates_alerts(self):
        items = [
            self._item("A", stock=20, demand=10),   # critical
            self._item("B", stock=200, demand=10),  # normal
        ]
        result = self.analyze(items)
        assert result["summary"]["critical_count"] >= 1

    def test_analyze_generates_replenishment_orders(self):
        items = [self._item("A", stock=5, demand=10, lead=3)]
        result = self.analyze(items)
        assert len(result["replenishment_orders"]) >= 1

    def test_analyze_summary_keys(self):
        items = [self._item()]
        result = self.analyze(items)
        for k in ["total_skus", "critical_count", "low_count", "total_inventory_value"]:
            assert k in result["summary"]

    def test_forecast_returns_forecast(self):
        history = [10.0, 11.0, 9.0, 12.0, 10.5, 11.0, 9.5]
        result = self.forecast(history, 7)
        assert len(result["forecast"]) == 7
        assert result["daily_avg"] > 0

    def test_forecast_trend_increasing(self):
        history = [15.0, 14.0, 13.0, 10.0, 9.0, 8.0, 7.0]  # 越来越大（newest first）
        result = self.forecast(history, 7)
        assert result["trend"] == "increasing"

    def test_forecast_short_history(self):
        result = self.forecast([5.0], 7)
        assert result["confidence"] == "low"


class TestRouteOptimizer:
    def setup_method(self):
        from tools.route_optimizer import DeliveryStop, optimize_route, detect_delay_risk
        self.Stop = DeliveryStop
        self.optimize = optimize_route
        self.detect = detect_delay_risk

    def _stop(self, sid, lat, lon, demand=1.0):
        return self.Stop(stop_id=sid, name=f"站点{sid}", lat=lat, lon=lon, demand=demand)

    def test_distance_calculation(self):
        a = self._stop("A", 31.23, 121.47, 1)  # 上海
        b = self._stop("B", 39.91, 116.39, 1)  # 北京
        dist = a.distance_to(b)
        assert 1000 < dist < 1500  # 大约1100km

    def test_optimize_empty_stops(self):
        depot = self._stop("DEPOT", 31.23, 121.47)
        result = self.optimize(depot, [])
        assert result.stops_count == 0
        assert result.total_distance_km == 0

    def test_optimize_single_stop(self):
        depot = self._stop("DEPOT", 31.23, 121.47)
        stop = self._stop("S1", 31.30, 121.50)
        result = self.optimize(depot, [stop])
        assert result.stops_count == 1
        assert result.total_distance_km > 0

    def test_optimize_returns_to_depot(self):
        depot = self._stop("DEPOT", 31.23, 121.47)
        stops = [self._stop(f"S{i}", 31.23 + i * 0.01, 121.47 + i * 0.01) for i in range(3)]
        result = self.optimize(depot, stops)
        assert result.route[0] == "DEPOT"
        assert result.route[-1] == "DEPOT"

    def test_optimize_visits_all_stops(self):
        depot = self._stop("DEPOT", 31.23, 121.47)
        stops = [self._stop(f"S{i}", 31.23 + i * 0.01, 121.47 + i * 0.01) for i in range(5)]
        result = self.optimize(depot, stops)
        assert result.stops_count == 5

    def test_to_dict_keys(self):
        depot = self._stop("DEPOT", 31.23, 121.47)
        stops = [self._stop("S1", 31.25, 121.50)]
        result = self.optimize(depot, stops)
        d = result.to_dict()
        for k in ["配送顺序", "总距离(km)", "预计耗时(h)", "站点数"]:
            assert k in d


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize_input
        self.sanitize = _sanitize_input

    def test_removes_control_chars(self):
        assert "\x00" not in self.sanitize("正常\x00攻击")

    def test_truncates(self):
        assert len(self.sanitize("A" * 5000)) <= 3000
