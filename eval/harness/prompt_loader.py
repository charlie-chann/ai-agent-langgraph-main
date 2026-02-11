"""
步骤 2：Prompt 版本化

从 eval/prompts/rag_v1.txt / rag_v2.txt 加载文本，
注入 RAG Agent，并重置 LangGraph 图。
支持 project_01 与 project_00。
"""
from __future__ import annotations

import sys

from .paths import PROMPTS_DIR, resolve_rag_project


def _wrap_v00_prompt(prompt_text: str) -> str:
    """project_00 rag_prompt expects kg_context + conflicts placeholders."""
    if "{kg_context}" in prompt_text:
        return prompt_text
    return (
        prompt_text.rstrip()
        + "\n\nKnowledge graph evidence:\n{kg_context}\n\n{conflicts}"
    )


def apply_rag_prompt_version(version: str, project: str = "00") -> str:
    prompt_file = PROMPTS_DIR / f"rag_{version}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt 版本不存在: {prompt_file}")

    prompt_text = prompt_file.read_text(encoding="utf-8")
    rag_root = str(resolve_rag_project(project))
    if rag_root not in sys.path:
        sys.path.insert(0, rag_root)

    if project in ("00", "project_00_rag_agent"):
        import app.agent.prompts.rag as rag_prompts
        import app.services.agent_service as rag_agent
    else:
        import prompts.rag_prompts as rag_prompts
        import agent as rag_agent

    system_text = _wrap_v00_prompt(prompt_text) if project in ("00", "project_00_rag_agent") else prompt_text
    rag_prompts.RAG_SYSTEM = system_text

    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    rag_prompts.rag_prompt = ChatPromptTemplate.from_messages([
        ("system", rag_prompts.RAG_SYSTEM),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{question}"),
    ])

    rag_agent.reset_graph("rag")
    return prompt_text
