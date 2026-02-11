"""tests/test_agent.py — Unit tests for project_07_finance_agent"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
import pytest


def _load(module_name: str, rel_path: str):
    path = Path(__file__).parent.parent / rel_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── analysis_tool tests ────────────────────────────────────────────────────────
class TestDCF:
    def setup_method(self):
        self.mod = _load("analysis_tool", "tools/analysis_tool.py")

    def test_basic_dcf(self):
        result = self.mod.calculate_dcf.invoke({
            "free_cash_flow": 5_000_000_000,
            "growth_rate": 0.10,
            "terminal_growth_rate": 0.03,
            "discount_rate": 0.10,
            "years": 5,
        })
        data = json.loads(result)
        assert "total_intrinsic_value" in data
        assert data["total_intrinsic_value"] > 0

    def test_dcf_invalid_rates(self):
        result = self.mod.calculate_dcf.invoke({
            "free_cash_flow": 1_000_000,
            "growth_rate": 0.05,
            "terminal_growth_rate": 0.10,  # > discount_rate — invalid
            "discount_rate": 0.08,
            "years": 5,
        })
        assert "Error" in result

    def test_dcf_has_projected_cashflows(self):
        result = self.mod.calculate_dcf.invoke({
            "free_cash_flow": 1_000_000,
            "growth_rate": 0.08,
            "terminal_growth_rate": 0.02,
            "discount_rate": 0.10,
            "years": 3,
        })
        data = json.loads(result)
        assert len(data["projected_cash_flows"]) == 3


class TestFundamentals:
    def setup_method(self):
        self.mod = _load("analysis_tool", "tools/analysis_tool.py")

    def test_good_metrics_pass(self):
        metrics = {
            "pe": 20, "pb": 2.5, "roe": 0.18, "net_margin": 0.12,
            "debt_to_equity": 50, "current_ratio": 2.0,
            "revenue_growth": 0.12, "earnings_growth": 0.15, "beta": 1.1,
        }
        result = self.mod.analyse_fundamentals.invoke(json.dumps(metrics))
        data = json.loads(result)
        assert "overall_rating" in data
        assert data["overall_rating"] in {"Strong Buy", "Buy", "Hold", "Sell"}

    def test_bad_metrics_sell(self):
        metrics = {
            "pe": 120, "pb": 20, "roe": -0.05, "net_margin": -0.10,
            "debt_to_equity": 500, "current_ratio": 0.5,
            "revenue_growth": -0.15, "earnings_growth": -0.30, "beta": 2.5,
        }
        result = self.mod.analyse_fundamentals.invoke(json.dumps(metrics))
        data = json.loads(result)
        assert data["overall_rating"] in {"Sell", "Hold"}

    def test_missing_data_handled(self):
        result = self.mod.analyse_fundamentals.invoke(json.dumps({"pe": 15}))
        data = json.loads(result)
        assert "analysis" in data

    def test_invalid_json_returns_error(self):
        result = self.mod.analyse_fundamentals.invoke("not valid json {{{")
        assert "Invalid JSON" in result or "Error" in result


class TestPortfolioMetrics:
    def setup_method(self):
        self.mod = _load("analysis_tool", "tools/analysis_tool.py")

    def _portfolio(self):
        return json.dumps([
            {"ticker": "AAPL", "weight": 0.30, "beta": 1.2, "sector": "Technology"},
            {"ticker": "JPM",  "weight": 0.40, "beta": 1.1, "sector": "Financial"},
            {"ticker": "JNJ",  "weight": 0.30, "beta": 0.7, "sector": "Healthcare"},
        ])

    def test_portfolio_beta_calculated(self):
        result = self.mod.calculate_portfolio_metrics.invoke(self._portfolio())
        data = json.loads(result)
        assert "portfolio_beta" in data
        assert data["portfolio_beta"] is not None

    def test_concentration_warning_triggered(self):
        heavy = json.dumps([
            {"ticker": "AAPL", "weight": 0.70, "beta": 1.2, "sector": "Technology"},
            {"ticker": "JPM",  "weight": 0.30, "beta": 1.0, "sector": "Financial"},
        ])
        result = self.mod.calculate_portfolio_metrics.invoke(heavy)
        data = json.loads(result)
        assert any("20%" in w or "concentration" in w.lower() for w in data.get("warnings", []))


# ── compliance_tool tests ──────────────────────────────────────────────────────
class TestCompliance:
    def setup_method(self):
        self.mod = _load("compliance_tool", "tools/compliance_tool.py")

    def test_compliant_position(self):
        result = self.mod.check_position_compliance.invoke({"ticker": "AAPL", "weight": 0.10})
        data = json.loads(result)
        assert "✅ PASS" in data["status"] or data["violations"] == 0

    def test_oversized_position_fails(self):
        result = self.mod.check_position_compliance.invoke({"ticker": "AAPL", "weight": 0.50})
        data = json.loads(result)
        assert data["violations"] > 0

    def test_esg_flagged_ticker(self):
        result = self.mod.check_position_compliance.invoke({"ticker": "BTI", "weight": 0.05})
        data = json.loads(result)
        assert data["warnings"] > 0 or "ESG" in str(data["checks"])

    def test_full_portfolio_screening(self):
        portfolio = json.dumps([
            {"ticker": "AAPL", "weight": 0.20, "sector": "Technology"},
            {"ticker": "MSFT", "weight": 0.20, "sector": "Technology"},
            {"ticker": "JPM",  "weight": 0.20, "sector": "Financial"},
            {"ticker": "JNJ",  "weight": 0.20, "sector": "Healthcare"},
            {"ticker": "XOM",  "weight": 0.20, "sector": "Energy"},
        ])
        result = self.mod.screen_portfolio_compliance.invoke(portfolio)
        data = json.loads(result)
        assert "overall_status" in data
        assert "positions_screened" in data
        assert data["positions_screened"] == 5

    def test_overweight_sector_flagged(self):
        heavy_tech = json.dumps([
            {"ticker": "AAPL", "weight": 0.25, "sector": "Technology"},
            {"ticker": "MSFT", "weight": 0.25, "sector": "Technology"},
            {"ticker": "GOOGL","weight": 0.25, "sector": "Technology"},
            {"ticker": "JPM",  "weight": 0.25, "sector": "Financial"},
        ])
        result = self.mod.screen_portfolio_compliance.invoke(heavy_tech)
        data = json.loads(result)
        assert any("Technology" in v and "75" in v or "sector" in v.lower() for v in data.get("violations", []) + data.get("warnings", []))

    def test_compliance_rules_returned(self):
        result = self.mod.get_compliance_rules.invoke(None)
        data = json.loads(result)
        assert "position_limits" in data
        assert "esg_exclusion_categories" in data


# ── report_tool tests ──────────────────────────────────────────────────────────
class TestReportTool:
    def setup_method(self):
        self.mod = _load("report_tool", "tools/report_tool.py")

    def test_save_and_list(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.mod, "_REPORTS", tmp_path)
        save_result = self.mod.save_report.invoke({"title": "test_report", "content": "# Test\nContent here"})
        assert "✅" in save_result or "saved" in save_result.lower()
        list_result = self.mod.list_reports.invoke(None)
        data = json.loads(list_result)
        assert len(data) == 1
        assert "test_report" in data[0]["filename"]

    def test_read_nonexistent(self):
        result = self.mod.read_report.invoke("nonexistent_report_xyz.md")
        assert "not found" in result.lower() or "Error" in result
