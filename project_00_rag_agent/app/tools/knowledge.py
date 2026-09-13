"""知识库相关 Agent Tools（LangChain @tool，供 ReAct / bind_tools 使用）。"""
from __future__ import annotations

from langchain_core.tools import tool

from app.knowledge.conflict import detect_conflicts, format_conflicts
from app.knowledge.retriever import retrieve_with_kg


def _format_docs(docs) -> str:
    """将检索到的文档格式化为带序号与来源的文本片段。"""
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
    """在内部知识库中检索与问题相关的文档。

    当用户询问公司政策、产品或已上传文档时使用。

    Args:
        query: 自然语言检索查询。
        user_roles: 逗号分隔的 ACL 角色（如 viewer,public 或 admin,public）。

    Returns:
        排序后的文档片段及可选的知识图谱上下文。
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
