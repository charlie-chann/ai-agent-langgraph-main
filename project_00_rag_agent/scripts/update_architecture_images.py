#!/usr/bin/env python3
"""将 architecture.md 中的 mermaid 块替换为 PNG 图片引用。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "architecture.md"

NAMES = [
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

TITLES = [
    "六层架构总览",
    "Streamlit UI 流程",
    "Eval Harness 流程",
    "HTTP 网关入口",
    "JWT + RBAC",
    "缓存与限流",
    "ask() 同步问答",
    "ask_stream() 流式",
    "HITL resume",
    "启动预热",
    "LangGraph 主图",
    "RagState 字段流转",
    "Checkpointer + HITL",
    "检索全流程",
    "入库全流程",
    "冲突检测",
    "知识图谱",
    "Provider + 熔断",
    "超时控制",
    "上下文压缩",
    "Docker 拓扑",
    "会话存储 conversation_id",
]


def main() -> None:
    """将 architecture.md 中的 mermaid 块替换为 PNG 图片引用。"""
    text = MD_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"```mermaid\n.*?```", re.DOTALL)
    blocks = pattern.findall(text)
    if len(blocks) != len(NAMES):
        raise SystemExit(f"Expected {len(NAMES)} mermaid blocks, found {len(blocks)}")

    for i, block in enumerate(blocks):
        name = NAMES[i]
        title = TITLES[i]
        png = ROOT / "docs" / "diagrams" / f"{name}.png"
        if not png.exists():
            raise SystemExit(f"Missing {png}")
        replacement = (
            f"![{title}](./diagrams/{name}.png)\n\n"
            f"<details>\n<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>\n\n"
            f"{block}\n\n</details>"
        )
        text = text.replace(block, replacement, 1)

    # 文首说明
    header_note = (
        "> **流程图已导出为 PNG**：见 [`docs/diagrams/`](./diagrams/)。"
        "修改图源文件 `docs/diagrams/source/*.mmd` 后执行 "
        "`python scripts/render_diagrams.py` 重新生成。\n\n"
    )
    if "流程图已导出为 PNG" not in text:
        text = text.replace(
            "> 生产级 RAG Agent",
            header_note + "> 生产级 RAG Agent",
            1,
        )

    MD_PATH.write_text(text, encoding="utf-8")
    print(f"Updated {MD_PATH} with {len(NAMES)} image references.")


if __name__ == "__main__":
    main()
