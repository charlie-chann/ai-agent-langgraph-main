"""
步骤 5：从 Agent state 收集 trace，并做失败归因
"""
from __future__ import annotations

from typing import Any


def build_trace(state: dict[str, Any]) -> list[dict[str, Any]]:
    """把 RAG state 压成统一 trace 结构，便于跨项目扩展。"""
    trace: list[dict[str, Any]] = []

    if state.get("rewritten_question"):
        trace.append({
            "step": "rewrite",
            "query": state.get("rewritten_question"),
        })

    docs = state.get("context_docs") or []
    trace.append({
        "step": "retrieve",
        "doc_count": len(docs),
        "sources": state.get("sources") or [],
    })

    trace.append({
        "step": "generate",
        "answer_preview": (state.get("answer") or "")[:200],
    })

    trace.append({
        "step": "grade",
        "grade": state.get("grade"),
        "reason": state.get("grade_reason"),
        "iterations": state.get("iterations"),
    })

    return trace


def attribute_failure(case: dict, scores: dict, result: dict) -> str:
    """简单失败归因标签，用于聚合报告。"""
    if result.get("error"):
        return "runtime_error"

    if case.get("must_refuse_or_unknown"):
        if scores.get("refuse_score", 0) < 1.0:
            return "should_refuse_but_answered"
        return "ok"

    if scores.get("contains_hit", 0) < 1.0 and scores.get("source_hit", 0) < 1.0:
        return "retrieval_or_generation_miss"

    if scores.get("contains_hit", 0) < 1.0:
        return "answer_content_miss"

    if scores.get("source_hit", 0) < 1.0:
        return "citation_miss"

    judge_pass = scores.get("judge_pass")
    if judge_pass is False:
        return "judge_fail"

    return "ok"


def summarize_failures(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = row.get("fail_reason", "ok")
        if reason == "ok":
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))
