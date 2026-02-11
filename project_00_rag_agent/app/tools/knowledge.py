"""知识库相关 Agent Tools（LangChain @tool，供 ReAct / bind_tools 使用）。"""
from __future__ import annotations

from langchain_core.tools import tool

from app.knowledge.conflict import detect_conflicts, format_conflicts
from app.knowledge.retriever import retrieve_with_kg


def _format_docs(docs) -> str:
    if not docs:
        return "No documents found."
    lines = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        snippet = (doc.page_content or "")[:500]
        lines.append(f"[{i}] ({source}) {snippet}")
    return "\n".join(lines)


@tool(parse_docstring=True)
def search_knowledge_base(query: str, user_roles: str = "viewer,public") -> str:
    """Search the internal knowledge base for documents relevant to a question.

    Use when the user asks about company policies, products, or uploaded documents.

    Args:
        query: Natural-language search query.
        user_roles: Comma-separated ACL roles (e.g. viewer,public or admin,public).

    Returns:
        Ranked document snippets and optional knowledge-graph context.
    """
    roles = [r.strip() for r in user_roles.split(",") if r.strip()]
    docs, kg_context = retrieve_with_kg(query, user_roles=roles or None)
    body = _format_docs(docs)
    conflicts = format_conflicts(detect_conflicts(docs)) if docs else ""
    parts = [body]
    if kg_context:
        parts.append(f"\nKnowledge graph:\n{kg_context}")
    if conflicts:
        parts.append(f"\nConflicts:\n{conflicts}")
    return "\n".join(parts).strip()
