# tools/symptom_checker.py — 症状分析与分诊工具
from __future__ import annotations
import re
from dataclasses import dataclass, field


# ── 症状 → 紧急度评分规则 ──────────────────────────────────────────────────────
# 每条规则: (关键词列表, 紧急度分数, 疑似科室, 说明)
_SYMPTOM_RULES: list[tuple[list[str], int, str, str]] = [
    # 急诊 (8-10分)
    (["胸痛", "心绞痛"], 10, "心内科", "可能为急性心肌梗死，需立即就诊"),
    (["呼吸困难", "喘不过气", "憋气"], 9, "急诊", "严重呼吸障碍，需紧急处理"),
    (["昏迷", "失去意识", "意识不清"], 10, "急诊", "意识障碍，危及生命"),
    (["大出血", "出血不止", "喷射性出血"], 10, "急诊", "严重出血，需立即止血处理"),
    (["严重过敏", "过敏性休克", "全身皮疹+呼吸困难"], 10, "急诊", "过敏性休克风险"),
    (["中风", "口歪眼斜", "偏瘫", "突发单侧无力"], 10, "神经内科", "疑似脑卒中，需立即送医"),
    (["高烧", "高热", "体温超过39"], 8, "急诊", "高热可能引发惊厥，需紧急处理"),

    # 紧急 (5-7分)
    (["骨折", "骨头断了", "关节脱位"], 7, "骨科", "疑似骨折或脱位，需 X 光检查"),
    (["腹痛剧烈", "急性腹痛", "腹部绞痛"], 7, "消化科", "疑似急腹症，需紧急评估"),
    (["高血压", "血压升高", "头痛+恶心"], 6, "心内科", "高血压危象风险"),
    (["糖尿病", "血糖异常", "低血糖", "血糖高"], 5, "内分泌科", "血糖异常，需尽快就诊"),
    (["发烧", "发热", "体温38"], 5, "内科", "发热需排查感染源"),
    (["持续咳嗽", "咳血", "血痰"], 7, "呼吸科", "咳血需排查肺部疾病"),
    (["头晕", "眩晕", "转", "走路不稳"], 5, "神经内科", "眩晕需排查神经系统问题"),

    # 常规 (1-4分)
    (["감기", "鼻塞", "流鼻涕", "打喷嚏"], 2, "内科", "疑似普通感冒"),
    (["皮疹", "皮肤痒", "皮肤红"], 3, "皮肤科", "皮肤过敏或感染"),
    (["腰痛", "腰酸", "背痛"], 3, "骨科", "肌肉劳损或腰椎问题"),
    (["失眠", "睡眠不好", "入睡困难"], 2, "神经内科", "睡眠障碍"),
    (["消化不良", "胃不舒服", "胃胀", "反酸"], 3, "消化科", "消化系统不适"),
    (["眼睛不适", "眼红", "视力模糊"], 3, "眼科", "眼科相关症状"),
]


@dataclass
class TriageResult:
    """分诊结果数据类。"""
    symptoms: list[str]
    urgency_score: int
    urgency_level: str        # "emergency" | "urgent" | "routine"
    recommended_dept: str
    explanation: str
    matched_rules: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "症状": self.symptoms,
            "紧急度评分": self.urgency_score,
            "紧急程度": self.urgency_level,
            "建议科室": self.recommended_dept,
            "说明": self.explanation,
            "匹配规则": self.matched_rules,
        }


def _mask_pii(text: str) -> str:
    """脱敏患者个人信息（姓名、身份证、手机号）。"""
    text = re.sub(r'1[3-9]\d{9}', '***手机号***', text)
    text = re.sub(r'\d{15}(\d{3})?', '***身份证***', text)
    text = re.sub(r'(患者|病人)?[李王张刘陈杨赵黄周吴徐孙朱马胡][a-zA-Z\u4e00-\u9fff]{1,3}', '***姓名***', text)
    return text


def triage(symptoms_text: str, mask_pii: bool = True) -> TriageResult:
    """
    根据症状文本进行分诊评估。

    Args:
        symptoms_text: 患者描述的症状（自由文本）
        mask_pii: 是否脱敏个人信息

    Returns:
        TriageResult: 分诊结果
    """
    if mask_pii:
        symptoms_text = _mask_pii(symptoms_text)

    text_lower = symptoms_text.lower()
    max_score = 0
    best_dept = "内科"
    best_explanation = "请前往内科就诊"
    matched = []
    extracted_symptoms: list[str] = []

    for keywords, score, dept, explanation in _SYMPTOM_RULES:
        for kw in keywords:
            if kw in text_lower or kw in symptoms_text:
                if score > max_score:
                    max_score = score
                    best_dept = dept
                    best_explanation = explanation
                matched.append(kw)
                if kw not in extracted_symptoms:
                    extracted_symptoms.append(kw)
                break  # 每条规则只匹配一次

    # 确定紧急程度
    if max_score >= 8:
        urgency_level = "emergency"
    elif max_score >= 5:
        urgency_level = "urgent"
    else:
        urgency_level = "routine"
        if max_score == 0:
            max_score = 1
            best_explanation = "症状较轻，建议常规预约就诊"

    return TriageResult(
        symptoms=extracted_symptoms or [symptoms_text[:50]],
        urgency_score=max_score,
        urgency_level=urgency_level,
        recommended_dept=best_dept,
        explanation=best_explanation,
        matched_rules=matched,
    )
