"""
knowledge/kg_extractor.py — 基于 LLM 的 NER + 关系抽取（知识图谱增强）

【职责】
1. 调用 Chat LLM 从 chunk 文本中抽取结构化三元组 JSON
2. 与 knowledge_graph 中的规则抽取组合，形成 hybrid 流水线
3. 按 settings.kg_extraction_mode 控制仅用规则、仅用 LLM 或两者合并

【设计原因】
1. 规则抽取快、成本低，适合格式规整的政策/制度文档
2. LLM 抽取覆盖长尾表述与隐含关系，质量高但有延迟与成本
3. hybrid 去重 (s,p,o)：同一关系不重复入库，规则结果优先保留顺序
4. 文本截断 2000 字符：控制 LLM token 消耗，长 chunk 仍可由规则部分覆盖
"""
from __future__ import annotations

import json
import re
from typing import List

from langchain_core.documents import Document
from loguru import logger

from app.core.config import settings
from app.core.timeouts import run_with_timeout
from app.infrastructure.providers.factory import get_chat_model
from app.knowledge.knowledge_graph import Triple

# LLM 抽取用的 Prompt 模板；要求仅返回 JSON 数组，便于正则 + json.loads 解析
EXTRACT_PROMPT = """Extract entities and relations from the text below.
Return JSON array only, each item: {{"subject":"...", "predicate":"...", "object":"..."}}
Use predicates: defines, applies_to, supersedes, effective_from, references, mentions.
Text:
{text}
"""


def extract_triples_llm(chunk: Document) -> List[Triple]:
    """
    使用 Chat LLM 作为 NER + 关系抽取器。

    从模型回复中用正则提取 [...] JSON 数组；解析失败或字段缺失时跳过该条。
    任意异常返回空列表，不阻断 ingest 主流程。
    """
    text = chunk.page_content[:2000]
    source = chunk.metadata.get("source", "unknown")
    doc_date = chunk.metadata.get("doc_date", chunk.metadata.get("loaded_at", ""))
    doc_type = chunk.metadata.get("doc_type", "general")

    try:
        llm = get_chat_model()
        msg = run_with_timeout(
            lambda: llm.invoke(EXTRACT_PROMPT.format(text=text)),
            timeout=min(settings.llm_timeout, 15.0),
            label="kg_extract",
        )
        raw = msg.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        triples: List[Triple] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            s = str(item.get("subject", "")).strip()
            p = str(item.get("predicate", "mentions")).strip()
            o = str(item.get("object", "")).strip()
            if s and o:
                triples.append(Triple(s, p, o, source, doc_date, doc_type))
        return triples
    except Exception as e:
        logger.warning(f"LLM KG extraction failed: {e}")
        return []


def extract_triples_hybrid(chunk: Document, rule_fn) -> List[Triple]:
    """
    组合规则抽取 + LLM 抽取，按 (subject, predicate, object) 去重。

    Args:
        chunk: 待抽取的文档块
        rule_fn: 规则抽取函数，通常为 knowledge_graph.extract_triples_from_chunk

    settings.kg_extraction_mode:
        - "rule"：仅规则
        - "llm"：仅 LLM
        - "hybrid"（默认）：两者都跑，去重合并
    """
    seen = set()
    out: List[Triple] = []

    for fn in (rule_fn, extract_triples_llm):
        if fn is rule_fn and settings.kg_extraction_mode == "llm":
            continue
        if fn is extract_triples_llm and settings.kg_extraction_mode == "rule":
            continue
        for t in fn(chunk):
            key = (t.subject, t.predicate, t.obj)
            if key not in seen:
                seen.add(key)
                out.append(t)
    return out
