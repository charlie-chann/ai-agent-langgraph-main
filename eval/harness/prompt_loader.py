"""
步骤 2：Prompt 版本化

从 eval/prompts/rag_v1.txt / rag_v2.txt 加载文本，
注入 project_01 的 RAG_SYSTEM，并重置 LangGraph 图。
"""
from __future__ import annotations

import importlib
import sys

from .paths import PROMPTS_DIR, RAG_PROJECT


def apply_rag_prompt_version(version: str) -> str:
    """
    加载 eval/prompts/rag_{version}.txt 并应用到 RAG Agent。

    Args:
        version: 例如 "v1" 或 "v2"（对应 rag_v1.txt）

    Returns:
        加载后的 prompt 文本（便于写入结果元数据）
    """
    prompt_file = PROMPTS_DIR / f"rag_{version}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt 版本不存在: {prompt_file}")

    prompt_text = prompt_file.read_text(encoding="utf-8")

    # 确保能 import project_01
    rag_root = str(RAG_PROJECT)
    if rag_root not in sys.path:
        sys.path.insert(0, rag_root)

    import prompts.rag_prompts as rag_prompts
    import agent as rag_agent

    # 注入版本化 Prompt（保留 {context} 占位符）
    rag_prompts.RAG_SYSTEM = prompt_text

    # 重建 ChatPromptTemplate，否则 LangChain 仍用旧 system 文本
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    rag_prompts.rag_prompt = ChatPromptTemplate.from_messages([
        ("system", rag_prompts.RAG_SYSTEM),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{question}"),
    ])

    # 图是单例，改 Prompt 后必须 reset
    rag_agent.reset_graph()

    return prompt_text
