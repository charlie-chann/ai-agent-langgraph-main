# tests/test_agent.py — project_17_ops_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest


class TestLogAnalyzer:
    def setup_method(self):
        from tools.log_analyzer import analyze_logs, parse_logs
        self.analyze = analyze_logs
        self.parse = parse_logs

    _sample_logs = """
2024-01-15T10:00:01 INFO [api-gateway] Request received: GET /api/users
2024-01-15T10:00:02 ERROR [auth-service] Connection refused: database timeout
2024-01-15T10:00:03 ERROR [auth-service] Connection refused: database timeout
2024-01-15T10:00:04 ERROR [auth-service] Connection refused: database timeout
2024-01-15T10:00:05 WARN [api-gateway] Retry attempt 1/3
2024-01-15T10:00:06 ERROR [user-service] NullPointerException in UserController
2024-01-15T10:00:07 INFO [api-gateway] Request completed: 500
"""

    def test_parse_extracts_events(self):
        events = self.parse(self._sample_logs)
        assert len(events) > 0

    def test_parse_detects_errors(self):
        events = self.parse(self._sample_logs)
        errors = [e for e in events if e.level == "ERROR"]
        assert len(errors) >= 3

    def test_parse_detects_warnings(self):
        events = self.parse(self._sample_logs)
        warnings = [e for e in events if e.level == "WARN"]
        assert len(warnings) >= 1

    def test_analyze_db_timeout_root_cause(self):
        logs = """
2024-01-15T10:00:01 ERROR [db] database connection timeout
2024-01-15T10:00:02 ERROR [db] database connection timeout
2024-01-15T10:00:03 ERROR [db] database error: query failed
"""
        result = self.analyze(logs)
        assert "数据库" in result.root_cause

    def test_analyze_oom_root_cause(self):
        logs = """
2024-01-15T10:00:01 ERROR [app] Out of memory: Java heap space
2024-01-15T10:00:02 FATAL [app] OOM Killer invoked
"""
        result = self.analyze(logs)
        assert "内存" in result.root_cause or "OOM" in result.root_cause

    def test_analyze_ticket_id_format(self):
        result = self.analyze(self._sample_logs)
        assert result.ticket_id.startswith("OPS-")

    def test_analyze_severity_classification(self):
        result = self.analyze(self._sample_logs)
        assert result.severity in ("critical", "major", "minor")

    def test_analyze_recommendations_not_empty(self):
        result = self.analyze(self._sample_logs)
        assert len(result.recommendations) > 0

    def test_to_dict_keys(self):
        result = self.analyze(self._sample_logs)
        d = result.to_dict()
        for k in ["工单ID", "严重程度", "根因分析", "受影响服务", "错误数", "处理建议"]:
            assert k in d

    def test_clean_logs_minor_severity(self):
        clean_logs = """
2024-01-15T10:00:01 INFO [app] Server started successfully
2024-01-15T10:00:02 INFO [app] Listening on port 8080
"""
        result = self.analyze(clean_logs)
        assert result.severity == "minor"
        assert result.error_count == 0

    def test_many_errors_critical(self):
        error_logs = "\n".join(
            f"2024-01-15T10:00:{i:02d} ERROR [svc] database timeout"
            for i in range(15)
        )
        result = self.analyze(error_logs)
        assert result.severity == "critical"


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize
        self.sanitize = _sanitize

    def test_removes_control_chars(self):
        assert "\x00" not in self.sanitize("文本\x00注入")

    def test_truncates_long_text(self):
        assert len(self.sanitize("A" * 100000)) <= 50000
