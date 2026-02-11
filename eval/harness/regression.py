"""
步骤 6：baseline 回归门禁

对比本次 eval 汇总指标与 eval/baseline.json，主指标下降超过阈值则 FAIL。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_TOLERANCE = 0.02


def load_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_baseline(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def check_regression(
    summary: dict[str, Any],
    baseline: dict[str, Any],
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    base_metrics = baseline.get("metrics", {})
    new_metrics = summary.get("metrics", {})

    regressions: list[dict[str, Any]] = []
    for key, base_val in base_metrics.items():
        if not isinstance(base_val, (int, float)):
            continue
        new_val = new_metrics.get(key)
        if new_val is None:
            continue
        if new_val < base_val - tolerance:
            regressions.append({
                "metric": key,
                "baseline": base_val,
                "current": new_val,
                "drop": round(base_val - new_val, 4),
            })

    return {
        "pass": len(regressions) == 0,
        "regressions": regressions,
        "tolerance": tolerance,
    }
