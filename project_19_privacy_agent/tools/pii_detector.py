# tools/pii_detector.py — PII 检测与脱敏工具（本地隐私 Agent）
from __future__ import annotations

import re
from dataclasses import dataclass, field


# PII 检测规则：(类型, 正则, 脱敏替换)
_PII_RULES: list[tuple[str, re.Pattern, str]] = [
    ("手机号", re.compile(r'\b1[3-9]\d{9}\b'), "***手机号***"),
    ("身份证", re.compile(r'(?<!\d)\d{15}(?:\d{3})?(?!\d)'), "***身份证***"),
    ("邮箱", re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'), "***邮箱***"),
    ("银行卡", re.compile(r'\b\d{16,19}\b'), "***银行卡***"),
    ("IP地址", re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), "***IP地址***"),
    ("社会信用代码", re.compile(r'\b[0-9A-HJ-NP-RT-Y]{18}\b'), "***统一社会信用代码***"),
    ("护照号", re.compile(r'\b[EGH][A-Z0-9]{8}\b'), "***护照***"),
]


@dataclass
class PIIResult:
    """PII 检测结果。"""
    original_text: str
    masked_text: str
    detected: list[dict]  # [{type, count, positions}]
    risk_level: str       # "high" | "medium" | "low" | "clean"

    def to_dict(self) -> dict:
        return {
            "原始长度": len(self.original_text),
            "已脱敏文本": self.masked_text,
            "检测到的PII类型": self.detected,
            "风险等级": self.risk_level,
        }


def detect_and_mask(text: str, mask: bool = True) -> PIIResult:
    """
    检测文本中的 PII 并按需脱敏。

    Args:
        text: 输入文本
        mask: 是否脱敏（True=脱敏，False=只报告不脱敏）

    Returns:
        PIIResult
    """
    if len(text) > 50000:
        text = text[:50000]

    masked = text
    detected = []
    total_pii_count = 0

    for pii_type, pattern, replacement in _PII_RULES:
        matches = list(pattern.finditer(text))
        if matches:
            count = len(matches)
            total_pii_count += count
            detected.append({
                "类型": pii_type,
                "数量": count,
                "示例位置": [[m.start(), m.end()] for m in matches[:3]],
            })
            if mask:
                masked = pattern.sub(replacement, masked)

    if total_pii_count == 0:
        risk_level = "clean"
    elif total_pii_count <= 2:
        risk_level = "low"
    elif total_pii_count <= 10:
        risk_level = "medium"
    else:
        risk_level = "high"

    return PIIResult(
        original_text=text,
        masked_text=masked if mask else text,
        detected=detected,
        risk_level=risk_level,
    )


def audit_log(action: str, user: str, data_hash: str, result: str,
              log_path: str = "logs/audit.log") -> None:
    """写入审计日志（本地文件，不上传）。"""
    import os
    from datetime import datetime
    from pathlib import Path

    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    entry = (
        f'{datetime.now().isoformat(timespec="seconds")} '
        f'user={user} action={action} data_hash={data_hash} result={result}\n'
    )
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)
