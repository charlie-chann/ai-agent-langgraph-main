# tests/test_agent.py — project_19_privacy_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest


class TestPIIDetector:
    def setup_method(self):
        from tools.pii_detector import detect_and_mask
        self.detect = detect_and_mask

    def test_detects_phone_number(self):
        result = self.detect("联系电话 13812345678")
        assert result.risk_level != "clean"
        assert any(d["类型"] == "手机号" for d in result.detected)

    def test_masks_phone_number(self):
        result = self.detect("手机 13812345678", mask=True)
        assert "13812345678" not in result.masked_text
        assert "***手机号***" in result.masked_text

    def test_detects_email(self):
        result = self.detect("邮件 user@example.com 请联系")
        assert any(d["类型"] == "邮箱" for d in result.detected)

    def test_masks_email(self):
        result = self.detect("发邮件到 admin@company.com 吧", mask=True)
        assert "admin@company.com" not in result.masked_text

    def test_detects_ip_address(self):
        result = self.detect("服务器 IP 192.168.1.100")
        assert any(d["类型"] == "IP地址" for d in result.detected)

    def test_no_pii_clean_level(self):
        result = self.detect("今天天气不错，适合出门散步")
        assert result.risk_level == "clean"
        assert len(result.detected) == 0

    def test_multiple_pii_high_risk(self):
        text = " ".join([
            "13800138000", "13900139000", "13700137000",
            "user1@a.com", "user2@b.com", "user3@c.com",
            "192.168.1.1", "192.168.1.2", "192.168.1.3",
            "1380013800", "13000130001", "14000140001",  # extra phones
        ])
        result = self.detect(text)
        assert result.risk_level in ("high", "medium")

    def test_no_mask_preserves_original(self):
        text = "手机号是13812345678"
        result = self.detect(text, mask=False)
        assert result.masked_text == text

    def test_to_dict_structure(self):
        result = self.detect("联系 13812345678")
        d = result.to_dict()
        for k in ["原始长度", "已脱敏文本", "检测到的PII类型", "风险等级"]:
            assert k in d

    def test_long_text_handled(self):
        long_text = "A" * 60000
        result = self.detect(long_text)
        assert result is not None

    def test_id_card_detected(self):
        result = self.detect("身份证110101199001011234")
        assert any(d["类型"] == "身份证" for d in result.detected)


class TestAgentPIIScanRun:
    def setup_method(self):
        from agent import run_pii_scan
        self.scan = run_pii_scan

    def test_scan_returns_dict(self):
        result = self.scan("测试文本 13812345678")
        assert isinstance(result, dict)
        assert "风险等级" in result

    def test_scan_masks_by_default(self):
        result = self.scan("手机 13812345678")
        assert "13812345678" not in result.get("已脱敏文本", "13812345678")


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize
        self.sanitize = _sanitize

    def test_removes_control_chars(self):
        assert "\x00" not in self.sanitize("text\x00injection")

    def test_truncates(self):
        assert len(self.sanitize("A" * 100000)) <= 50000
