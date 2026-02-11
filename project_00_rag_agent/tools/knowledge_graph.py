"""
tools/knowledge_graph.py — 知识图谱：实体/关系存储与证据链检索

【职责】
1. 从文档 chunk 中抽取 (subject, predicate, object) 三元组
2. 持久化图谱（pickle + JSON 导出），供问答时补充结构化证据
3. 按用户问题做简单 token/子串匹配，召回相关三元组并格式化为 Prompt 上下文

【设计原因】
1. 规则 + LLM 混合抽取（见 kg_extractor）：规则快且可控，LLM 补全复杂关系
2. 与向量检索并行：向量找「段落」，KG 找「实体关系」，互补增强可解释性
3. entity_sources 记录实体出处，便于冲突检测与溯源（见 conflict.py）
4. demo 级 ENTITY_PATTERNS / RELATION_KEYWORDS 可替换为正式 NER/RE 流水线
"""
from __future__ import annotations

import json
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from langchain_core.documents import Document
from loguru import logger

from config import settings

# ── 规则抽取用的模式与关系词表 ────────────────────────────────────────────────
# 生产环境可替换为 spaCy/HanLP/专用 NER 模型
ENTITY_PATTERNS = [
    (r"《([^》]+)》", "policy"),
    (r"(\d{4}-\d{2}-\d{2})", "date"),
    (r"(\d+\s*天)", "duration"),
]
RELATION_KEYWORDS = {
    "规定": "defines",
    "适用于": "applies_to",
    "废止": "supersedes",
    "生效": "effective_from",
    "引用": "references",
}


@dataclass
class Triple:
    """知识图谱中的一条三元组，附带来源文档与时间元数据。"""
    subject: str
    predicate: str
    obj: str
    source: str = ""
    doc_date: str = ""
    doc_type: str = ""


@dataclass
class KnowledgeGraph:
    """
    内存中的轻量知识图谱。

    triples：全部三元组列表
    entity_sources：实体 → 来源文档集合，用于冲突与溯源分析
    """
    triples: List[Triple] = field(default_factory=list)
    entity_sources: Dict[str, Set[str]] = field(default_factory=dict)

    def add_triple(self, t: Triple) -> None:
        """追加三元组并更新 entity_sources 索引。"""
        self.triples.append(t)
        for ent in (t.subject, t.obj):
            self.entity_sources.setdefault(ent, set()).add(t.source)

    def query(self, question: str, top_k: int = settings.kg_top_k) -> List[Triple]:
        """
        按问题与三元组文本的词重叠 + 中文实体子串匹配打分，返回 Top-K。

        中文场景下纯分词 overlap 可能为 0，因此对 subject/obj 做子串命中兜底。
        """
        q_lower = question.lower()
        q_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", q_lower))
        scored: List[Tuple[float, Triple]] = []
        for t in self.triples:
            text = f"{t.subject} {t.predicate} {t.obj}".lower()
            t_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", text))
            overlap = len(q_tokens & t_tokens)
            # 中文实体子串匹配（如问题含「年假」而三元组 subject 为「年假」）
            if not overlap:
                for ent in (t.subject, t.obj):
                    if ent and ent.lower() in q_lower:
                        overlap = 1
                        break
            if overlap:
                scored.append((overlap, t))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:top_k]]

    def to_context(self, triples: List[Triple]) -> str:
        """
        将三元组列表格式化为可注入 LLM Prompt 的文本块。

        无匹配三元组时返回空字符串，调用方无需特殊分支。
        """
        if not triples:
            return ""
        lines = ["[Knowledge Graph Evidence]"]
        for t in triples:
            lines.append(f"- ({t.subject}) --[{t.predicate}]--> ({t.obj}) [source: {t.source}]")
        return "\n".join(lines)

    def save(self, path: Optional[Path] = None) -> None:
        """序列化整个 KnowledgeGraph 到 pickle 文件。"""
        path = path or settings.kg_dir / "graph.pkl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"KG saved: {len(self.triples)} triples → {path}")

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "KnowledgeGraph":
        """从 pickle 加载；文件不存在时返回空图。"""
        path = path or settings.kg_dir / "graph.pkl"
        if not path.exists():
            return cls()
        with open(path, "rb") as f:
            kg = pickle.load(f)
        logger.info(f"KG loaded: {len(kg.triples)} triples")
        return kg


# ── 进程级 KG 单例 ────────────────────────────────────────────────────────────
_kg: Optional[KnowledgeGraph] = None


def get_kg() -> KnowledgeGraph:
    """获取知识图谱单例，首次调用时从磁盘 load。"""
    global _kg
    if _kg is None:
        _kg = KnowledgeGraph.load()
    return _kg


def extract_triples_from_chunk(chunk: Document) -> List[Triple]:
    """
    基于规则从单个 chunk 抽取三元组（快速、可解释、无 LLM 成本）。

    流程：
    1. ENTITY_PATTERNS 正则抓实体
    2. RELATION_KEYWORDS 在文中出现时，用前后实体凑 (s, p, o)
    3. 「A 规定 B」句式单独正则匹配
    """
    text = chunk.page_content
    source = chunk.metadata.get("source", "unknown")
    doc_date = chunk.metadata.get("doc_date", chunk.metadata.get("loaded_at", ""))
    doc_type = chunk.metadata.get("doc_type", "general")
    triples: List[Triple] = []

    entities: List[str] = []
    for pattern, _ in ENTITY_PATTERNS:
        entities.extend(re.findall(pattern, text))

    for kw, pred in RELATION_KEYWORDS.items():
        if kw in text:
            # 简化策略：subject = 第一个实体，object = 第二个（若存在）
            if len(entities) >= 2:
                triples.append(Triple(entities[0], pred, entities[1], source, doc_date, doc_type))
            elif len(entities) == 1:
                triples.append(Triple(entities[0], pred, "related_entity", source, doc_date, doc_type))

    # 显式「A 规定 B」句式
    for m in re.finditer(r"([^\s，,。]{2,30})\s*规定\s*([^\s，,。]{2,50})", text):
        triples.append(Triple(m.group(1), "defines", m.group(2), source, doc_date, doc_type))

    return triples


def ingest_chunks_to_kg(chunks: List[Document]) -> int:
    """
    批量将 chunk 三元组写入内存 KG 并持久化。

    使用 kg_extractor.extract_triples_hybrid 合并规则与 LLM 结果。
    完成后 save pickle 并 export_json 便于人工审计。

    Returns:
        本次新增三元组条数（含重复写入前的计数，非去重后净增）
    """
    from tools.kg_extractor import extract_triples_hybrid

    kg = get_kg()
    count = 0
    for chunk in chunks:
        triples = extract_triples_hybrid(chunk, extract_triples_from_chunk)
        for t in triples:
            kg.add_triple(t)
            count += 1
    kg.save()
    export_json()
    return count


def export_json(path: Optional[Path] = None) -> str:
    """
    将当前 KG 导出为 JSON 文件，便于调试与非 Python 工具消费。

    Returns:
        导出文件的绝对路径字符串
    """
    kg = get_kg()
    path = path or settings.kg_dir / "graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {"s": t.subject, "p": t.predicate, "o": t.obj, "source": t.source, "date": t.doc_date}
        for t in kg.triples
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
