#!/usr/bin/env python3
"""从 docs/architecture.md 提取 Mermaid 图并渲染为 PNG。"""
from __future__ import annotations

import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "architecture.md"
OUT_DIR = ROOT / "docs" / "diagrams"
SRC_DIR = OUT_DIR / "source"

# 与 architecture.md 章节对应的文件名（00 为全项目端到端总览，须为第一个 mermaid 块）
NAMES = [
    "00_project_end_to_end",
    "01_layers_overview",
    "02_streamlit_ui",
    "03_eval_harness",
    "04_http_gateway",
    "05_jwt_rbac",
    "06_cache_rate_limit",
    "07_ask_sync",
    "08_ask_stream",
    "09_hitl_resume",
    "10_startup",
    "11_langgraph_main",
    "12_rag_state_flow",
    "13_checkpointer_hitl",
    "14_retrieval",
    "15_ingest",
    "16_conflict",
    "17_knowledge_graph",
    "18_provider_circuit_breaker",
    "19_timeouts",
    "20_compression",
    "21_docker_topology",
    "22_conversations",
]


def extract_mermaid_blocks(text: str) -> list[str]:
    """从 Markdown 文本中提取所有 mermaid 代码块内容。"""
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    return [m.group(1).strip() for m in pattern.finditer(text)]


def render_kroki(mermaid: str, out_png: Path) -> bool:
    """通过 Kroki 公共服务渲染 PNG（需网络）。"""
    req = urllib.request.Request(
        "https://kroki.io/mermaid/png",
        data=mermaid.encode("utf-8"),
        headers={"Content-Type": "text/plain"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_png.write_bytes(resp.read())
        return True
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"  Kroki failed: {e}", file=sys.stderr)
        return False


def render_mmdc(mmd_path: Path, out_png: Path) -> bool:
    """本地 mermaid-cli 渲染。"""
    try:
        subprocess.run(
            [
                "npx", "--yes", "@mermaid-js/mermaid-cli",
                "-i", str(mmd_path),
                "-o", str(out_png),
                "-b", "white",
                "-w", "1200",
            ],
            check=True,
            capture_output=True,
            cwd=str(ROOT),
            timeout=120,
        )
        return out_png.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  mmdc failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    """提取 architecture.md 中的 Mermaid 图并渲染为 PNG。"""
    text = MD_PATH.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(text)
    if not blocks:
        print("No mermaid blocks found.")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    if len(blocks) != len(NAMES):
        print(f"Warning: {len(blocks)} diagrams vs {len(NAMES)} names; using auto names for extras.")

    ok, fail = 0, 0
    for i, block in enumerate(blocks):
        name = NAMES[i] if i < len(NAMES) else f"diagram_{i+1:02d}"
        mmd_path = SRC_DIR / f"{name}.mmd"
        png_path = OUT_DIR / f"{name}.png"
        mmd_path.write_text(block + "\n", encoding="utf-8")

        print(f"Rendering {name}...")
        if render_mmdc(mmd_path, png_path) or render_kroki(block, png_path):
            print(f"  -> {png_path.relative_to(ROOT)}")
            ok += 1
        else:
            fail += 1

    print(f"\nDone: {ok} ok, {fail} failed -> {OUT_DIR}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
