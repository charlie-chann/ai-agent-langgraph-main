#!/usr/bin/env python3
"""
步骤 7：单变量 Prompt 迭代 — 对比两次 eval 结果

用法：
  python eval/harness/compare.py \
    --a eval/results/rag_v1_xxx.json \
    --b eval/results/rag_v2_xxx.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare two eval result files")
    parser.add_argument("--a", required=True, help="baseline result json")
    parser.add_argument("--b", required=True, help="candidate result json")
    args = parser.parse_args()

    a = load(Path(args.a))
    b = load(Path(args.b))

    ma, mb = a["summary"]["metrics"], b["summary"]["metrics"]
    print("=== Prompt A/B Compare ===")
    print(f"A: prompt={a.get('prompt_version')} file={args.a}")
    print(f"B: prompt={b.get('prompt_version')} file={args.b}")
    print()

    for key in sorted(set(ma) | set(mb)):
        va, vb = ma.get(key), mb.get(key)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = round(vb - va, 4)
            sign = "+" if delta >= 0 else ""
            print(f"  {key}: {va} -> {vb} ({sign}{delta})")

    # 逐题 diff
    by_id_a = {r["id"]: r for r in a["rows"]}
    by_id_b = {r["id"]: r for r in b["rows"]}
    print("\n=== Per-case total_score delta ===")
    for cid in sorted(set(by_id_a) | set(by_id_b)):
        sa = by_id_a.get(cid, {}).get("scores", {}).get("total_score")
        sb = by_id_b.get(cid, {}).get("scores", {}).get("total_score")
        if sa is None or sb is None:
            continue
        delta = round(sb - sa, 4)
        if delta != 0:
            print(f"  {cid}: {sa} -> {sb} ({delta:+}) reasonB={by_id_b[cid].get('fail_reason')}")


if __name__ == "__main__":
    main()
