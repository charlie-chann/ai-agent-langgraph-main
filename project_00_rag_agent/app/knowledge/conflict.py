"""
knowledge/conflict.py — 文档冲突检测（metadata + 内容对比）

【职责】
1. 对检索到的多个 chunk 按「主题」分组，发现同一主题下内容不一致的情况
2. 根据 doc_date、doc_type 等 metadata 计算优先级，给出 resolution_hint
3. 格式化为 Prompt 片段，提醒 LLM 在回答中说明冲突与推荐依据

【设计原因】
1. 企业知识库常有多版本制度/FAQ，向量检索可能同时命中新旧文档
2. 显式冲突提示可降低 LLM「把两段矛盾内容都当真」的风险
3. _meta_priority：日期越新、doc_type 越权威（policy > general）越优先
4. 按 topic 或内容前 40 字分桶：轻量启发式，无需额外 NLP 模型
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from langchain_core.documents import Document


@dataclass
class ConflictItem:
    """单条冲突记录：同一主题下两段不同表述及推荐解析方向。"""
    topic: str
    value_a: str
    value_b: str
    source_a: str
    source_b: str
    resolution_hint: str


def _meta_priority(doc: Document) -> tuple:
    """
    文档优先级排序键：值越大越「应被采纳」。

    比较顺序：(doc_date, type_score)
    - doc_date：字符串 ISO 日期，较新者排前（reverse=True）
    - type_score：policy/regulation/faq/general 分级权重
    """
    md = doc.metadata or {}
    date = md.get("doc_date", md.get("loaded_at", ""))
    dtype = md.get("doc_type", "general")
    type_score = {"policy": 3, "regulation": 2, "faq": 1, "general": 0}.get(dtype, 0)
    return (date, type_score)


def detect_conflicts(docs: List[Document]) -> List[ConflictItem]:
    """
    在检索结果中查找「同一主题、不同内容」的 chunk 对。

    【分桶逻辑】
    metadata.topic 优先；否则用 page_content 前 40 字符作为简易主题 key。

    【冲突判定】
    同桶至少 2 条且正文不完全相同 → 记为冲突；
    value_a 取优先级更高者，value_b 为次优者。
    """
    buckets: dict[str, List[Document]] = {}
    for doc in docs:
        key = doc.metadata.get("topic") or doc.page_content[:40].strip()
        buckets.setdefault(key, []).append(doc)

    conflicts: List[ConflictItem] = []
    for topic, group in buckets.items():
        if len(group) < 2:
            continue
        sorted_docs = sorted(group, key=_meta_priority, reverse=True)
        a, b = sorted_docs[0], sorted_docs[1]
        if a.page_content.strip() == b.page_content.strip():
            continue
        hint = f"Prefer newer/higher-priority: {a.metadata.get('source', '?')}"
        conflicts.append(
            ConflictItem(
                topic=topic[:80],
                value_a=a.page_content[:200],
                value_b=b.page_content[:200],
                source_a=a.metadata.get("source", "unknown"),
                source_b=b.metadata.get("source", "unknown"),
                resolution_hint=hint,
            )
        )
    return conflicts


def format_conflicts(conflicts: List[ConflictItem]) -> str:
    """
    将冲突列表格式化为可注入 LLM 的多行文本。

    无冲突时返回空字符串。
    """
    if not conflicts:
        return ""
    lines = ["[⚠ Document Conflicts Detected]"]
    for i, c in enumerate(conflicts, 1):
        lines.append(
            f"{i}. Topic: {c.topic}\n"
            f"   A [{c.source_a}]: {c.value_a[:120]}...\n"
            f"   B [{c.source_b}]: {c.value_b[:120]}...\n"
            f"   Resolution: {c.resolution_hint}"
        )
    return "\n".join(lines)
