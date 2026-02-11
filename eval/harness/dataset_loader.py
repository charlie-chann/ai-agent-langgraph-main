"""
步骤 1：加载评测集

jsonl 每行一条样本，字段见 eval/datasets/rag_qa.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_dataset(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSONL at line {line_no}: {e}") from e
    if not cases:
        raise ValueError(f"Dataset is empty: {path}")
    return cases
