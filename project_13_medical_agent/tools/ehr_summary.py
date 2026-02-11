# tools/ehr_summary.py — 电子健康档案(EHR)摘要工具
from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class EHRSummary:
    """EHR 摘要数据类。"""
    patient_id: str
    chief_complaint: str
    vital_signs: dict
    diagnoses: list[str]
    medications: list[str]
    allergies: list[str]
    risk_flags: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "患者ID": self.patient_id,
            "主诉": self.chief_complaint,
            "生命体征": self.vital_signs,
            "诊断": self.diagnoses,
            "用药": self.medications,
            "过敏史": self.allergies,
            "风险标记": self.risk_flags,
            "建议": self.recommendations,
        }


def _extract_vitals(text: str) -> dict:
    """从文本中提取生命体征数字。"""
    vitals: dict[str, str] = {}

    bp = re.search(r'血压\s*[：:]?\s*(\d{2,3}[/\/]\d{2,3})', text)
    if bp:
        vitals["血压"] = bp.group(1) + " mmHg"

    temp = re.search(r'体温\s*[：:]?\s*(\d{2,3}(?:\.\d)?)', text)
    if temp:
        vitals["体温"] = temp.group(1) + " °C"

    hr = re.search(r'心率\s*[：:]?\s*(\d{2,3})', text)
    if hr:
        vitals["心率"] = hr.group(1) + " 次/分"

    rr = re.search(r'呼吸\s*[：:]?\s*(\d{1,2})', text)
    if rr:
        vitals["呼吸频率"] = rr.group(1) + " 次/分"

    spo2 = re.search(r'血氧\s*[：:]?\s*(\d{2,3})', text)
    if spo2:
        vitals["血氧饱和度"] = spo2.group(1) + " %"

    return vitals


def _extract_medications(text: str) -> list[str]:
    """从文本中提取药物名称。"""
    common_drugs = [
        "阿司匹林", "格列本脲", "二甲双胍", "阿托伐他汀", "氨氯地平",
        "美托洛尔", "厄贝沙坦", "奥美拉唑", "布洛芬", "对乙酰氨基酚",
        "头孢", "青霉素", "阿莫西林", "克拉霉素", "氟喹诺酮",
        "地西泮", "氯硝西泮", "帕罗西汀", "舍曲林", "利培酮",
        "胰岛素", "左甲状腺素", "氢化可的松", "泼尼松",
    ]
    found = []
    for drug in common_drugs:
        if drug in text and drug not in found:
            found.append(drug)
    # 提取"XX mg"格式的药物
    for m in re.finditer(r'([^\s，。、]{2,8})\s*\d+\s*mg', text):
        name = m.group(1)
        if name not in found:
            found.append(name)
    return found


def _detect_risk_flags(text: str, diagnoses: list[str], vitals: dict) -> list[str]:
    """检测高风险标记。"""
    flags = []
    risk_words = [
        ("恶性肿瘤", "癌症或肿瘤病史"),
        ("心肌梗死", "心肌梗死病史"),
        ("糖尿病", "糖尿病患者需监测血糖"),
        ("高血压", "高血压需监测血压"),
        ("肾功能不全", "肾功能异常，用药需谨慎"),
        ("肝功能异常", "肝功能异常，用药需谨慎"),
        ("过敏", "存在过敏史"),
        ("手术", "近期手术史"),
    ]
    for keyword, flag_msg in risk_words:
        if keyword in text or any(keyword in d for d in diagnoses):
            flags.append(flag_msg)

    # 生命体征风险检测
    bp_str = vitals.get("血压", "")
    if bp_str:
        bp_match = re.match(r'(\d+)', bp_str)
        if bp_match and int(bp_match.group(1)) >= 160:
            flags.append("收缩压≥160 mmHg，高血压危象风险")

    temp_str = vitals.get("体温", "")
    if temp_str:
        temp_match = re.match(r'(\d{2,3}(?:\.\d)?)', temp_str)
        if temp_match and float(temp_match.group(1)) >= 39.0:
            flags.append("高热≥39°C")

    return list(dict.fromkeys(flags))  # 去重保序


def summarize_ehr(patient_id: str, raw_record: str) -> EHRSummary:
    """
    从原始医疗记录文本生成结构化 EHR 摘要。

    Args:
        patient_id: 患者 ID
        raw_record: 医疗记录原始文本

    Returns:
        EHRSummary: 结构化摘要
    """
    if len(raw_record) > 5000:
        raw_record = raw_record[:5000]

    vitals = _extract_vitals(raw_record)
    medications = _extract_medications(raw_record)

    # 提取主诉（第一句话或前50字）
    lines = [l.strip() for l in raw_record.split('\n') if l.strip()]
    chief_complaint = lines[0][:100] if lines else "无主诉记录"

    # 简单诊断提取
    diagnoses = []
    dx_patterns = [r'诊断[：:]\s*([^\n。；]{2,30})', r'印象[：:]\s*([^\n。；]{2,30})']
    for pat in dx_patterns:
        for m in re.finditer(pat, raw_record):
            diagnoses.append(m.group(1).strip())

    # 过敏史
    allergies: list[str] = []
    for m in re.finditer(r'过敏[：:]\s*([^\n。；]{2,30})', raw_record):
        allergies.append(m.group(1).strip())

    risk_flags = _detect_risk_flags(raw_record, diagnoses, vitals)

    # 基本建议
    recommendations = []
    if "糖尿病" in raw_record:
        recommendations.append("按时服用降糖药，定期监测血糖")
    if "高血压" in raw_record:
        recommendations.append("低盐饮食，规律服降压药")
    if not recommendations:
        recommendations.append("遵医嘱按时复诊")

    return EHRSummary(
        patient_id=patient_id,
        chief_complaint=chief_complaint,
        vital_signs=vitals,
        diagnoses=diagnoses,
        medications=medications,
        allergies=allergies,
        risk_flags=risk_flags,
        recommendations=recommendations,
    )
