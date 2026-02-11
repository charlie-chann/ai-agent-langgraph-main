#!/usr/bin/env python3
"""
步骤 3 + 4 + 5 + 6 + 7：Eval Harness 主入口

用法示例：
  # 跑 v1，规则分 + LLM Judge
  python eval/harness/run_eval.py --prompt v1

  # 单变量迭代：只改 Prompt 后跑 v2 并做回归
  python eval/harness/run_eval.py --prompt v2 --regression

  # 首次建立基线
  python eval/harness/run_eval.py --prompt v1 --update-baseline

  # 跳过 LLM Judge（无 Ollama 时）
  python eval/harness/run_eval.py --prompt v1 --no-judge
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 允许从仓库根目录运行
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eval.harness.dataset_loader import load_dataset
from eval.harness.judge import llm_judge
from eval.harness.metrics import score_rules
from eval.harness.paths import BASELINE_PATH, DATASETS_DIR, RESULTS_DIR
from eval.harness.prompt_loader import apply_rag_prompt_version
from eval.harness.regression import check_regression, load_baseline, save_baseline
from eval.harness.trace_analysis import attribute_failure, build_trace, summarize_failures


def _import_rag_ask(project: str):
    from eval.harness.paths import resolve_rag_project
    rag_root = str(resolve_rag_project(project))
    if rag_root not in sys.path:
        sys.path.insert(0, rag_root)
    from app.services.agent_service import ask
    return ask


def run_case(case: dict, ask_fn, use_judge: bool, project: str = "00") -> dict[str, Any]:
    t0 = time.perf_counter()
    kwargs: dict = {"return_state": True}
    if project == "00":
        kwargs["use_cache"] = False
        kwargs["user_roles"] = ["admin", "public"]
    out = ask_fn(case["question"], **kwargs)
    latency_ms = round((time.perf_counter() - t0) * 1000)

    state = out.get("state") or {}
    context = "\n\n".join(d.page_content for d in state.get("context_docs") or [])

    rule = score_rules(case, out)

    judge = {"judge_skipped": True, "judge_pass": None, "judge_score": None, "judge_reason": "disabled"}
    if use_judge:
        judge = llm_judge(case["question"], context, out.get("answer") or "")

    total_score = rule["rule_score"]
    if judge.get("judge_score") is not None:
        total_score = round(0.6 * rule["rule_score"] + 0.4 * float(judge["judge_score"]), 4)

    merged_scores = {**rule, **judge, "total_score": total_score}
    fail_reason = attribute_failure(case, merged_scores, out)

    return {
        "id": case["id"],
        "question": case["question"],
        "answer": out.get("answer"),
        "sources": out.get("sources"),
        "grade": out.get("grade"),
        "iterations": out.get("iterations"),
        "latency_ms": latency_ms,
        "error": out.get("error"),
        "trace": build_trace(state),
        "scores": merged_scores,
        "fail_reason": fail_reason,
        "tags": case.get("tags", []),
    }


def summarize(rows: list[dict]) -> dict[str, Any]:
    n = len(rows) or 1
    avg_total = sum(r["scores"]["total_score"] for r in rows) / n
    hit_rate = sum(1 for r in rows if r["scores"].get("contains_hit", 0) >= 1.0) / n

    judged = [r for r in rows if r["scores"].get("judge_pass") is not None]
    judge_pass_rate = (
        sum(1 for r in judged if r["scores"].get("judge_pass")) / len(judged)
        if judged else None
    )

    refuse_cases = [r for r in rows if "out_of_scope" in r.get("tags", []) or r.get("fail_reason") == "ok"]
    refuse_accuracy = None

    return {
        "count": len(rows),
        "metrics": {
            "avg_total_score": round(avg_total, 4),
            "hit_rate": round(hit_rate, 4),
            "judge_pass_rate": round(judge_pass_rate, 4) if judge_pass_rate is not None else None,
            "refuse_accuracy": refuse_accuracy,
            "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / n),
        },
        "failure_breakdown": summarize_failures(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RAG eval harness")
    parser.add_argument("--project", default="00", choices=["00", "01"], help="RAG 项目：00=production, 01=baseline")
    parser.add_argument("--dataset", default=str(DATASETS_DIR / "rag_qa.jsonl"))
    parser.add_argument("--prompt", default="v1", help="Prompt 版本：v1 / v2")
    parser.add_argument("--no-judge", action="store_true", help="跳过 LLM-as-Judge")
    parser.add_argument("--regression", action="store_true", help="对比 baseline 做回归门禁")
    parser.add_argument("--update-baseline", action="store_true", help="用本次结果更新 baseline.json")
    parser.add_argument("--tolerance", type=float, default=0.02)
    args = parser.parse_args()

    # ── 步骤 2：加载 Prompt 版本 ──
    prompt_text = apply_rag_prompt_version(args.prompt, project=args.project)
    print(f"[prompt] loaded rag_{args.prompt}.txt for project_{args.project}")

    # ── 步骤 1：加载评测集 ──
    cases = load_dataset(Path(args.dataset))
    print(f"[dataset] {len(cases)} cases from {args.dataset}")

    ask_fn = _import_rag_ask(args.project)

    # ── 步骤 3：批量跑 Agent ──
    rows: list[dict] = []
    for i, case in enumerate(cases, 1):
        print(f"[run] ({i}/{len(cases)}) {case['id']}: {case['question'][:40]}...")
        rows.append(run_case(case, ask_fn, use_judge=not args.no_judge, project=args.project))

    summary = summarize(rows)
    payload = {
        "suite": "rag_qa",
        "project": args.project,
        "prompt_version": args.prompt,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "rows": rows,
        "prompt_preview": prompt_text[:200],
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"rag_p{args.project}_{args.prompt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[saved] {out_path}")
    print(f"[metrics] {json.dumps(summary['metrics'], ensure_ascii=False)}")
    print(f"[failures] {summary['failure_breakdown']}")

    # ── 步骤 6：回归门禁 ──
    if args.update_baseline:
        save_baseline(BASELINE_PATH, {
            "suite": "rag_qa",
            "prompt_version": args.prompt,
            "metrics": summary["metrics"],
        })
        print(f"[baseline] updated -> {BASELINE_PATH}")
        return 0

    if args.regression:
        baseline = load_baseline(BASELINE_PATH)
        report = check_regression(summary, baseline, tolerance=args.tolerance)
        print(f"[regression] pass={report['pass']} details={report['regressions']}")
        return 0 if report["pass"] else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
