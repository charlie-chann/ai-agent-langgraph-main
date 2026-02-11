"""
步骤 4a：规则打分（不依赖 LLM，稳定、便宜）

根据评测集里的 expected_* 字段做 deterministic 评分。
"""
from __future__ import annotations

from typing import Any


REFUSE_KEYWORDS = [
    "未找到", "不知道", "无法", "没有相关", "insufficient", "not contain",
    "资料中未找到",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(k.lower() in text_lower for k in keywords if k)


def score_rules(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer") or ""
    sources = result.get("sources") or []
    source_text = " ".join(sources)

    expected_contains = case.get("expected_answer_contains") or []
    expected_sources = case.get("expected_sources") or []
    must_refuse = case.get("must_refuse_or_unknown", False)

    contains_hit = 1.0 if (not expected_contains or _contains_any(answer, expected_contains)) else 0.0
    source_hit = 1.0 if (not expected_sources or _contains_any(source_text, expected_sources)) else 0.0

    refused = _contains_any(answer, REFUSE_KEYWORDS)
    if must_refuse:
        refuse_score = 1.0 if refused else 0.0
    else:
        refuse_score = 1.0 if not refused else 0.5  # 正常题不应轻易拒答

    # 简单加权；可根据业务调整
    total = 0.5 * contains_hit + 0.3 * source_hit + 0.2 * refuse_score

    return {
        "contains_hit": contains_hit,
        "source_hit": source_hit,
        "refuse_score": refuse_score,
        "rule_score": round(total, 4),
        "refused": refused,
    }
