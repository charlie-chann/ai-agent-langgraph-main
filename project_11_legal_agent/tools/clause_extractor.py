# tools/clause_extractor.py — 合同条款结构化提取
"""
从合同文本中提取结构化信息：
- 合同当事人（甲方/乙方）
- 合同金额
- 合同期限
- 争议解决方式
- 管辖地
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ContractParties:
    party_a: str = ""    # 甲方
    party_b: str = ""    # 乙方
    contract_amount: str = ""
    contract_period: str = ""
    jurisdiction: str = ""
    dispute_resolution: str = ""
    signing_date: str = ""


def extract_parties(text: str) -> ContractParties:
    """从合同文本中提取当事方及关键数字信息。"""
    parties = ContractParties()

    # 甲方
    m = re.search(r'甲\s*方[：:]\s*(.{2,50}?)(?:\n|（|，|,)', text)
    if m:
        parties.party_a = m.group(1).strip()

    # 乙方
    m = re.search(r'乙\s*方[：:]\s*(.{2,50}?)(?:\n|（|，|,)', text)
    if m:
        parties.party_b = m.group(1).strip()

    # 合同金额
    m = re.search(r'(?:合同金额|总价|费用|报酬|薪资)[：:\s]*(?:人民币)?[\s]*([¥￥]?\d[\d,，.万千百]+\s*(?:元|万元|美元|USD)?)', text)
    if m:
        parties.contract_amount = m.group(1).strip()

    # 合同期限
    m = re.search(r'(?:合同期限|有效期|服务期)[：:\s]*(.{5,60}?)(?:\n|；|。)', text)
    if m:
        parties.contract_period = m.group(1).strip()

    # 管辖地
    m = re.search(r'(?:管辖|仲裁机构|争议.{0,10}提交)[：:\s]*(.{4,60}?)(?:\n|；|。|仲裁|法院)', text)
    if m:
        parties.jurisdiction = m.group(1).strip()

    # 争议解决
    if re.search(r'仲裁', text):
        parties.dispute_resolution = "仲裁"
    elif re.search(r'诉讼|人民法院', text):
        parties.dispute_resolution = "诉讼"
    else:
        parties.dispute_resolution = "未明确"

    # 签约日期
    m = re.search(r'(?:签订|签署|合同日期)[：:\s]*(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?)', text)
    if m:
        parties.signing_date = m.group(1).strip()

    return parties


def sanitize_contract_input(text: str) -> str:
    """清理合同输入：去除控制字符，防止 injection。"""
    if not text or not text.strip():
        raise ValueError("合同文本不能为空")
    # Remove control characters except whitespace
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
    # Injection pattern guard
    injection_patterns = [
        r'ignore\s+(previous|all)\s+instruction',
        r'<\|system\|>',
        r'\[INST\]',
    ]
    for pat in injection_patterns:
        if re.search(pat, text, re.IGNORECASE):
            raise ValueError("输入包含不允许的内容")
    return text.strip()
