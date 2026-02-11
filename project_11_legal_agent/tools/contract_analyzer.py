# tools/contract_analyzer.py — 合同条款风险分析工具（规则引擎）
"""
基于规则的合同风险分析：
- 霸王条款识别（单方面终止、无限赔偿、自动续约陷阱）
- 关键条款提取（支付条款、保密协议、知识产权归属）
- 风险评分（高风险/中风险/低风险）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger
from config import RISK_THRESHOLD_HIGH, RISK_THRESHOLD_MEDIUM, MAX_CONTRACT_CHARS

# ── 风险规则库 ────────────────────────────────────────────────────────────────
# 每条规则: (pattern, risk_level, category, description)
_RISK_RULES = [
    # 高风险条款
    (r"(单方面|任意).{0,10}(修改|变更|终止|解除)", "high", "单方权利", "甲方可单方面修改/终止合同"),
    (r"(无限制|不限于|无上限).{0,20}(赔偿|赔款|违约金)", "high", "无限赔偿", "赔偿金额无上限，风险极高"),
    (r"自动.{0,8}(续约|续期|延期).{0,20}(不得|不能)?.{0,10}(异议|取消|退出)", "high", "自动续约陷阱", "自动续约且难以退出"),
    (r"(放弃|豁免|不得主张).{0,20}(权利|索赔|赔偿|诉讼)", "high", "权利放弃", "当事人被要求放弃重要权利"),
    (r"知识产权.{0,30}(归属|所有).{0,20}(甲方|委托方|雇主)", "high", "IP归属损失", "所有知识产权归对方，作者无任何权益"),
    (r"(泄露|披露).{0,20}(个人信息|隐私|数据).{0,20}(第三方|合作方)", "high", "隐私风险", "可能向第三方披露个人信息"),

    # 中风险条款
    (r"(保密期限|保密义务).{0,30}(永久|终身|无期限)", "medium", "永久保密", "保密义务无期限，可能影响未来就业"),
    (r"(竞业禁止|竞业限制).{0,50}(2年|24个月|3年|36个月)", "medium", "竞业禁止", "竞业限制期过长"),
    (r"(违约金|赔偿金).{0,20}(\d+)\s*%.{0,10}(月薪|合同金额)", "medium", "高额违约金", "违约金比例较高"),
    (r"(争议|纠纷).{0,20}(仲裁|诉讼).{0,20}(不得|不能|禁止)", "medium", "争议解决限制", "限制争议解决方式"),
    (r"(服务|产品).{0,20}(质量|标准).{0,20}(自行认定|单方判断)", "medium", "质量标准主观", "质量标准由对方单方面认定"),

    # 低风险条款（提醒）
    (r"(定金|押金|保证金).{0,20}(\d+).{0,5}(元|万|百)", "low", "资金占用", "需要提前支付定金/押金"),
    (r"(管辖法院|仲裁机构).{0,30}(北京|上海|甲方所在)", "low", "管辖地风险", "争议解决地对己方不利"),
]

# 关键条款关键词（提取用）
_KEY_CLAUSE_PATTERNS = {
    "支付条款": r"(?:付款|支付|结算|费用|金额).{0,100}",
    "保密协议": r"(?:保密|机密|不得泄露).{0,150}",
    "知识产权": r"(?:知识产权|著作权|专利|商标|版权).{0,150}",
    "责任限制": r"(?:责任限制|赔偿上限|不承担|免责).{0,150}",
    "合同期限": r"(?:合同期限|有效期|服务期|期满).{0,100}",
    "终止条款": r"(?:终止|解除|解约).{0,150}",
}


@dataclass
class RiskItem:
    clause_text: str        # 触发的原文片段（最多200字）
    risk_level: str         # high | medium | low
    category: str           # 风险类别
    description: str        # 风险说明


@dataclass
class ContractAnalysisResult:
    total_risk_score: float         # 0.0 ~ 1.0
    risk_level: str                 # high | medium | low
    high_risks: list[RiskItem] = field(default_factory=list)
    medium_risks: list[RiskItem] = field(default_factory=list)
    low_risks: list[RiskItem] = field(default_factory=list)
    key_clauses: dict[str, str] = field(default_factory=dict)
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "total_risk_score": round(self.total_risk_score, 3),
            "risk_level": self.risk_level,
            "high_risks": [{"clause": r.clause_text[:200], "category": r.category, "description": r.description} for r in self.high_risks],
            "medium_risks": [{"clause": r.clause_text[:200], "category": r.category, "description": r.description} for r in self.medium_risks],
            "low_risks": [{"clause": r.clause_text[:200], "category": r.category, "description": r.description} for r in self.low_risks],
            "key_clauses": {k: v[:300] for k, v in self.key_clauses.items()},
            "recommendation": self.recommendation,
        }


def analyze_contract(contract_text: str, contract_type: str = "通用合同") -> ContractAnalysisResult:
    """
    对合同文本进行风险分析。
    
    Args:
        contract_text: 合同全文（最多 MAX_CONTRACT_CHARS 字符）
        contract_type: 合同类型（用于上下文理解）
    Returns: ContractAnalysisResult
    """
    if not contract_text or not contract_text.strip():
        raise ValueError("合同文本不能为空")

    text = contract_text.strip()[:MAX_CONTRACT_CHARS]
    logger.info(f"[analyze_contract] type={contract_type}, chars={len(text)}")

    high_risks, medium_risks, low_risks = [], [], []

    for pattern, risk_level, category, description in _RISK_RULES:
        full_pattern = r'.{0,50}' + pattern + r'.{0,50}'
        for m in re.finditer(full_pattern, text, re.DOTALL | re.IGNORECASE):
            match_text = m.group(0)
            item = RiskItem(
                clause_text=match_text.strip()[:200],
                risk_level=risk_level,
                category=category,
                description=description,
            )
            if risk_level == "high":
                if len(high_risks) < 10:
                    high_risks.append(item)
            elif risk_level == "medium":
                if len(medium_risks) < 10:
                    medium_risks.append(item)
            else:
                if len(low_risks) < 10:
                    low_risks.append(item)

    # 提取关键条款
    key_clauses = {}
    for clause_name, pattern in _KEY_CLAUSE_PATTERNS.items():
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        if matches:
            key_clauses[clause_name] = matches[0].strip()[:300]

    # 计算风险评分
    # 高风险 0.3/条，中风险 0.1/条，低风险 0.02/条，上限 1.0
    score = min(len(high_risks) * 0.3 + len(medium_risks) * 0.1 + len(low_risks) * 0.02, 1.0)

    if high_risks:
        risk_level = "high"
        recommendation = "⚠️ 合同中存在高风险条款，强烈建议咨询专业律师后再签署；必须重点关注并争取修改或删除高风险条款。"
    elif medium_risks or score >= RISK_THRESHOLD_MEDIUM:
        risk_level = "medium"
        recommendation = "⚡ 合同存在中等风险，建议对中风险条款进行协商修改，或寻求法律意见。"
    else:
        risk_level = "low"
        recommendation = "✅ 合同整体风险较低，建议仔细核对关键条款后可考虑签署。"

    return ContractAnalysisResult(
        total_risk_score=score,
        risk_level=risk_level,
        high_risks=high_risks,
        medium_risks=medium_risks,
        low_risks=low_risks,
        key_clauses=key_clauses,
        recommendation=recommendation,
    )


def generate_review_report(result: ContractAnalysisResult, contract_type: str = "合同") -> str:
    """将分析结果格式化为Markdown报告。"""
    lines = [
        f"# {contract_type} 审查报告",
        "",
        f"## 风险评级：{'🔴 高风险' if result.risk_level == 'high' else '🟡 中风险' if result.risk_level == 'medium' else '🟢 低风险'}",
        f"**综合风险分数：{result.total_risk_score:.2f}**",
        "",
        f"### 综合建议",
        result.recommendation,
        "",
    ]

    if result.high_risks:
        lines.append("## ⚠️ 高风险条款")
        for r in result.high_risks:
            lines.extend([f"### {r.category}", f"**{r.description}**", f"> {r.clause_text}", ""])

    if result.medium_risks:
        lines.append("## ⚡ 中风险条款")
        for r in result.medium_risks:
            lines.extend([f"### {r.category}", f"**{r.description}**", f"> {r.clause_text}", ""])

    if result.low_risks:
        lines.append("## ℹ️ 注意事项")
        for r in result.low_risks:
            lines.extend([f"- **{r.category}**：{r.description}", f"  > {r.clause_text}", ""])

    if result.key_clauses:
        lines.append("## 📋 关键条款摘要")
        for name, text in result.key_clauses.items():
            lines.extend([f"### {name}", f"> {text[:200]}", ""])

    return "\n".join(lines)
