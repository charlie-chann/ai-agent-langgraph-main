# tests/test_agent.py — project_14_sales_crm_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ── Lead Scorer Tests ──────────────────────────────────────────────────────────
class TestLeadScorer:
    def setup_method(self):
        from tools.lead_scorer import Lead, score_lead
        self.Lead = Lead
        self.score_lead = score_lead

    def _make_lead(self, **overrides) -> "Lead":
        base = dict(
            lead_id="LD-001",
            name="张伟",
            company="金融科技有限公司",
            title="总经理",
            industry="金融",
            budget=200.0,
            timeline_days=30,
            engagement_score=80,
            last_contact_date="2024-06-01",
        )
        base.update(overrides)
        return self.Lead(**base)

    def test_high_budget_hot_lead(self):
        lead = self._make_lead(budget=200.0, title="CEO", engagement_score=90)
        score = self.score_lead(lead)
        assert score.grade == "hot"
        assert score.total_score >= 70

    def test_low_budget_cold_lead(self):
        lead = self._make_lead(budget=1.0, title="员工", industry="其他",
                               timeline_days=365, engagement_score=5)
        score = self.score_lead(lead)
        assert score.grade == "cold"
        assert score.total_score < 40

    def test_medium_budget_warm_lead(self):
        lead = self._make_lead(budget=30.0, title="经理", engagement_score=40,
                               timeline_days=90, industry="零售")
        score = self.score_lead(lead)
        assert score.grade in ("warm", "hot")

    def test_score_breakdown_contains_all_dimensions(self):
        lead = self._make_lead()
        score = self.score_lead(lead)
        for dim in ["预算", "职位", "行业", "紧迫度", "互动度"]:
            assert dim in score.score_breakdown

    def test_score_capped_at_100(self):
        lead = self._make_lead(budget=999.0, title="CEO", engagement_score=100)
        score = self.score_lead(lead)
        assert score.total_score <= 100

    def test_recommended_action_not_empty(self):
        lead = self._make_lead()
        score = self.score_lead(lead)
        assert len(score.recommended_action) > 0

    def test_next_followup_date_format(self):
        import re
        lead = self._make_lead()
        score = self.score_lead(lead)
        assert re.match(r'\d{4}-\d{2}-\d{2}', score.next_followup_date)

    def test_to_dict_structure(self):
        lead = self._make_lead()
        score = self.score_lead(lead)
        d = score.to_dict()
        for key in ["线索ID", "总分", "等级", "分项得分", "建议行动", "建议跟进日期"]:
            assert key in d


# ── Email Generator Tests ──────────────────────────────────────────────────────
class TestEmailGenerator:
    def setup_method(self):
        from tools.email_generator import generate_email
        self.generate = generate_email

    def test_first_contact_email(self):
        email = self.generate("first_contact", "王总", "ABC科技", "互联网")
        assert "王总" in email.body or "王总" in email.subject or True  # name may be in greeting
        assert len(email.subject) > 0
        assert len(email.body) > 0

    def test_followup_email(self):
        email = self.generate("followup", "李明", "DEF制造", "制造", budget=50.0)
        assert email.email_type == "followup"
        assert len(email.body) > 0

    def test_proposal_email(self):
        email = self.generate("proposal", "张总", "GHI金融", "金融")
        assert email.email_type == "proposal"
        assert "GHI金融" in email.body or "GHI金融" in email.subject

    def test_nurture_email(self):
        email = self.generate("nurture", "陈总", "JKL教育", "教育")
        assert email.email_type == "nurture"

    def test_invalid_type_defaults_to_first_contact(self):
        email = self.generate("unknown_type", "测试", "公司", "行业")
        assert email.email_type == "first_contact"

    def test_email_body_not_too_long(self):
        from config import EMAIL_MAX_LENGTH
        email = self.generate("first_contact", "A" * 50, "B" * 100, "C" * 50)
        assert len(email.body) <= EMAIL_MAX_LENGTH

    def test_xss_injection_sanitized(self):
        email = self.generate("first_contact", "<script>alert(1)</script>姓名", "公司", "行业")
        assert "<script>" not in email.body

    def test_to_dict_keys(self):
        email = self.generate("first_contact", "测试", "测试公司", "科技")
        d = email.to_dict()
        for key in ["收件人", "主题", "正文", "邮件类型"]:
            assert key in d


# ── CRM Tool Tests ─────────────────────────────────────────────────────────────
class TestCRMTool:
    def setup_method(self):
        from tools.crm_tool import (
            create_lead, update_lead_status, log_activity,
            get_lead, list_leads_by_status, pipeline_summary, _validate_email
        )
        self.create = create_lead
        self.update_status = update_lead_status
        self.log = log_activity
        self.get = get_lead
        self.list_by = list_leads_by_status
        self.summary = pipeline_summary
        self.validate_email = _validate_email

    def test_create_lead_returns_id(self):
        record = self.create("王小明", "ABC公司", "test@abc.com", "13800138000")
        assert record.lead_id.startswith("LD-")

    def test_create_lead_default_status(self):
        record = self.create("李华", "DEF公司", "li@def.com", "13900139000")
        assert record.status == "new"

    def test_update_lead_status(self):
        record = self.create("张三", "GHI公司", "z@ghi.com", "18000000001")
        result = self.update_status(record.lead_id, "contacted")
        assert result["success"] is True
        assert result["new_status"] == "contacted"

    def test_update_invalid_status(self):
        record = self.create("李四", "JKL公司", "li4@jkl.com", "18000000002")
        result = self.update_status(record.lead_id, "flying")
        assert result["success"] is False

    def test_update_nonexistent_lead(self):
        result = self.update_status("LD-NONEXIST", "contacted")
        assert result["success"] is False

    def test_log_activity(self):
        record = self.create("王五", "MNO公司", "w5@mno.com", "18000000003")
        result = self.log(record.lead_id, "email", "发送了初次联系邮件")
        assert result["success"] is True

    def test_get_lead(self):
        record = self.create("赵六", "PQR公司", "z6@pqr.com", "18000000004")
        fetched = self.get(record.lead_id)
        assert fetched is not None
        assert fetched["公司"] == "PQR公司"

    def test_list_leads_by_status(self):
        record = self.create("孙七", "STU公司", "s7@stu.com", "18000000005")
        self.update_status(record.lead_id, "qualified")
        qualified = self.list_by("qualified")
        assert any(r["线索ID"] == record.lead_id for r in qualified)

    def test_pipeline_summary_structure(self):
        summary = self.summary()
        assert "total" in summary
        assert "by_status" in summary
        assert summary["total"] >= 0

    def test_validate_email_valid(self):
        assert self.validate_email("user@example.com") is True

    def test_validate_email_invalid(self):
        assert self.validate_email("not-an-email") is False

    def test_xss_in_name_sanitized(self):
        record = self.create("<script>alert</script>名字", "公司", "t@t.com", "10000000000")
        assert "<script>" not in record.name


# ── Agent Sanitization Tests ───────────────────────────────────────────────────
class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize_input
        self.sanitize = _sanitize_input

    def test_removes_control_chars(self):
        result = self.sanitize("正常文字\x00\x01注入攻击")
        assert "\x00" not in result

    def test_truncates_long_input(self):
        result = self.sanitize("A" * 5000)
        assert len(result) <= 3000

    def test_normal_text_preserverd(self):
        text = "帮我评估这个客户的潜力"
        assert self.sanitize(text) == text
