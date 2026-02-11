# tests/test_agent.py — project_13_medical_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import importlib.util


# ── Symptom Checker Tests ──────────────────────────────────────────────────────
class TestSymptomChecker:
    def setup_method(self):
        from tools.symptom_checker import triage, _mask_pii
        self.triage = triage
        self.mask_pii = _mask_pii

    def test_emergency_chest_pain(self):
        result = self.triage("突然胸痛，感觉心脏不舒服")
        assert result.urgency_level == "emergency"
        assert result.urgency_score >= 8

    def test_emergency_consciousness_loss(self):
        result = self.triage("患者昏迷，意识不清，无法唤醒")
        assert result.urgency_level == "emergency"

    def test_urgent_high_fever(self):
        result = self.triage("发烧，体温超过39度，头痛恶心")
        assert result.urgency_level in ("emergency", "urgent")

    def test_urgent_bone_fracture(self):
        result = self.triage("摔倒后手臂骨折，疼痛剧烈")
        assert result.urgency_level in ("urgent", "emergency")
        assert result.recommended_dept == "骨科"

    def test_routine_cold(self):
        result = self.triage("鼻塞，流鼻涕，打喷嚏，轻微不舒服")
        assert result.urgency_level == "routine"

    def test_routine_skin_rash(self):
        result = self.triage("皮肤痒，有皮疹")
        assert result.urgency_level == "routine"
        assert result.recommended_dept == "皮肤科"

    def test_returns_triage_result_structure(self):
        result = self.triage("头晕，走路不稳")
        d = result.to_dict()
        for key in ["症状", "紧急度评分", "紧急程度", "建议科室", "说明"]:
            assert key in d

    def test_mask_phone_number(self):
        masked = self.mask_pii("患者电话13812345678需要回访")
        assert "13812345678" not in masked
        assert "***手机号***" in masked

    def test_mask_id_card(self):
        masked = self.mask_pii("身份证号110101199001011234")
        assert "199001011234" not in masked

    def test_unknown_symptoms_routine(self):
        result = self.triage("感觉有点不舒服，说不清楚")
        # 无匹配规则应为 routine
        assert result.urgency_level == "routine"
        assert result.urgency_score >= 1

    def test_stroke_emergency(self):
        result = self.triage("突发口歪眼斜，右侧偏瘫，讲话困难")
        assert result.urgency_level == "emergency"


# ── Appointment Tool Tests ─────────────────────────────────────────────────────
class TestAppointmentTool:
    def setup_method(self):
        from tools.appointment_tool import book_appointment, cancel_appointment, query_appointment, _anonymize_patient_id
        self.book = book_appointment
        self.cancel = cancel_appointment
        self.query = query_appointment
        self.anonymize = _anonymize_patient_id

    def test_book_appointment_returns_id(self):
        appt = self.book("P001", "内科")
        assert appt.appointment_id.startswith("APT-")

    def test_book_appointment_has_date(self):
        appt = self.book("P002", "骨科")
        assert appt.appointment_date is not None
        assert len(appt.appointment_date) == 10  # YYYY-MM-DD

    def test_cancel_appointment(self):
        appt = self.book("P003", "心内科")
        result = self.cancel(appt.appointment_id)
        assert result["success"] is True

    def test_cancel_nonexistent(self):
        result = self.cancel("APT-NONEXIST")
        assert result["success"] is False

    def test_query_appointment(self):
        appt = self.book("P004", "眼科")
        queried = self.query(appt.appointment_id)
        assert queried is not None
        assert queried["就诊科室"] == "眼科"

    def test_anonymize_patient_id_removes_special_chars(self):
        clean = self.anonymize("P-001!@#")
        assert re.match(r'^[A-Z0-9]+$', clean) is not None, f"Expected alphanumeric ID, got {clean}"

    def test_appointment_to_dict_keys(self):
        appt = self.book("P005", "消化科")
        d = appt.to_dict()
        for key in ["预约编号", "患者ID", "就诊科室", "预约日期", "状态"]:
            assert key in d


# ── EHR Summary Tests ──────────────────────────────────────────────────────────
class TestEHRSummary:
    def setup_method(self):
        from tools.ehr_summary import summarize_ehr, _extract_vitals, _extract_medications
        self.summarize = summarize_ehr
        self.extract_vitals = _extract_vitals
        self.extract_meds = _extract_medications

    _sample_record = """
患者主诉：胸闷、气短2天，伴有血压升高。
诊断：高血压3级，疑似冠心病。
血压：165/95，体温：37.2，心率：92。
过敏：青霉素过敏。
用药：阿司匹林 100mg 每日一次，氨氯地平 5mg 每日一次。
手术史：2018年行阑尾切除术。
"""

    def test_extract_blood_pressure(self):
        vitals = self.extract_vitals("血压：140/90")
        assert "血压" in vitals
        assert "140/90" in vitals["血压"]

    def test_extract_temperature(self):
        vitals = self.extract_vitals("体温：38.5")
        assert "体温" in vitals
        assert "38.5" in vitals["体温"]

    def test_extract_medications(self):
        meds = self.extract_meds("患者服用阿司匹林和二甲双胍")
        assert "阿司匹林" in meds
        assert "二甲双胍" in meds

    def test_summarize_hypertension_flagged(self):
        summary = self.summarize("P100", self._sample_record)
        assert any("高血压" in f for f in summary.risk_flags)

    def test_summarize_allergy_extracted(self):
        summary = self.summarize("P100", self._sample_record)
        assert len(summary.allergies) > 0

    def test_summarize_medications_extracted(self):
        summary = self.summarize("P100", self._sample_record)
        assert len(summary.medications) > 0

    def test_summarize_to_dict_structure(self):
        summary = self.summarize("P100", self._sample_record)
        d = summary.to_dict()
        for key in ["患者ID", "主诉", "生命体征", "诊断", "用药", "过敏史", "风险标记", "建议"]:
            assert key in d

    def test_long_record_truncated(self):
        """超长记录应被截断而不崩溃。"""
        long_record = "患者主诉头晕。" * 1000  # ~7000字
        summary = self.summarize("P999", long_record)
        assert summary is not None


# ── Agent Input Sanitization Tests ────────────────────────────────────────────
class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize_input
        self.sanitize = _sanitize_input

    def test_removes_control_characters(self):
        result = self.sanitize("正常文本\x00\x01恶意插入")
        assert "\x00" not in result
        assert "\x01" not in result

    def test_truncates_long_input(self):
        long_input = "A" * 3000
        result = self.sanitize(long_input)
        assert len(result) <= 2000

    def test_normal_text_preserved(self):
        text = "患者胸痛，血压高，需要就诊"
        result = self.sanitize(text)
        assert result == text


import re  # needed for anonymize test
