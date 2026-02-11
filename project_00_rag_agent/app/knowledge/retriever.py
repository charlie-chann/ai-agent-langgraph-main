"""
knowledge/retriever.py — 生产级混合检索 + ACL + 知识图谱 + 降级兜底

【职责】
1. 管理 ChromaDB 向量库（持久化，语义检索）
2. 管理 BM25 索引（关键词检索，支持 pickle 持久化与 Chroma 重建）
3. 融合 BM25 + 向量两种召回结果（Hybrid Search）
4. Cross-Encoder 精排，提升 Top-K 质量
5. ACL 角色过滤，按用户权限裁剪可见文档
6. 可选挂载知识图谱上下文，供 Agent 引用证据链

【设计原因】
1. 单例缓存 _vectorstore / _bm25_retriever：避免每次问答重复连接 Chroma、重复构建 BM25
2. Hybrid：向量擅长「语义相近」，BM25 擅长「专有名词/数字精确匹配」，互补
3. 分数融合 0.4(BM25) + 0.6(向量)：向量权重略高，符合语义 RAG 主流实践
4. BM25 pickle 持久化：进程重启后无需重新 ingest 即可恢复 sparse/hybrid 能力
5. embed_breaker 熔断：Embedding 服务异常时降级为 BM25-only，保证服务可用
6. ACL 在 rerank 之前过滤：减少无效精排计算，同时保证用户看不到越权内容
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Callable, List, Optional

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from loguru import logger

from app.core.config import settings, CHROMA_DIR, COLLECTION_NAME, TOP_K, RETRIEVAL_MODE, RERANK_ENABLED, RERANK_MODEL
from app.core.circuit_breaker import embed_breaker
from app.infrastructure.providers.factory import get_embeddings
from app.knowledge.knowledge_graph import get_kg

# ── 进程级全局缓存 ────────────────────────────────────────────────────────────
# ChromaDB 数据在 chroma_db/ 目录，重启后仍可加载；
# BM25 索引优先从 pickle 恢复，缺失时可从 Chroma metadata 重建。
_vectorstore: Optional[Chroma] = None
_bm25_retriever: Optional[BM25Retriever] = None
_chunks: List[Document] = []  # BM25 需要的原始 chunk 列表
_reranker_model = None  # Cross-Encoder 懒加载，首次 rerank 时才加载


def _acl_filter(docs: List[Document], user_roles: Optional[List[str]]) -> List[Document]:
    """
    按 ACL 角色过滤检索结果。

    文档 metadata 中 acl_roles 默认为 ["public"]；
    用户角色与文档 acl 有交集，或文档含 public 时可见。
    未传 user_roles 时不做过滤（向后兼容内部调用）。
    """
    if not user_roles:
        return docs
    role_set = set(user_roles)
    out = []
    for d in docs:
        acl = d.metadata.get("acl_roles", ["public"])
        if isinstance(acl, str):
            acl = [acl]
        if "public" in acl or role_set.intersection(acl):
            out.append(d)
    return out


def get_vectorstore(force_reload: bool = False) -> Chroma:
    """
    获取 Chroma 向量库单例。

    首次调用时连接本地 chroma_db/ 目录；若目录不存在会在首次 ingest 时创建。
    embedding 通过 providers.factory 统一获取，支持 Ollama/OpenAI 等切换。
    """
    global _vectorstore
    if _vectorstore is None or force_reload:
        embeddings = get_embeddings()
        _vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
        )
        logger.info(f"VectorStore loaded from {CHROMA_DIR}")
    return _vectorstore


def persist_bm25(chunks: List[Document]) -> None:
    """
    将 BM25 所需的 chunk 列表序列化到磁盘。

    路径由 settings.bm25_index_path 配置，便于容器挂载与备份。
    """
    path = settings.bm25_index_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(chunks, f)
    logger.info(f"BM25 index persisted: {len(chunks)} chunks")


def load_bm25_from_disk() -> List[Document]:
    """
    从 pickle 文件加载 BM25 chunk 列表。

    文件不存在时返回空列表，调用方需降级或触发 rebuild。
    """
    path = settings.bm25_index_path
    if not path.exists():
        return []
    with open(path, "rb") as f:
        chunks = pickle.load(f)
    logger.info(f"BM25 index loaded: {len(chunks)} chunks")
    return chunks


def set_chunks(chunks: List[Document]) -> None:
    """
    更新 BM25 使用的 chunk 列表，重建内存索引并持久化到磁盘。

    每次 ingest 新文档时必须调用，否则 hybrid/sparse 模式的 BM25 部分为空或过旧。
    k 设为 TOP_K * 2：为后续融合与 rerank 预留更大候选池。
    """
    global _chunks, _bm25_retriever
    _chunks = chunks
    if chunks:
        _bm25_retriever = BM25Retriever.from_documents(chunks)
        _bm25_retriever.k = TOP_K * 2
    persist_bm25(chunks)


def get_bm25_retriever() -> Optional[BM25Retriever]:
    """
    获取 BM25 检索器。依赖 _chunks 已在 ingest 或 load 时填充。

    若内存为空，尝试从 pickle 加载；仍为空则返回 None。
    """
    global _bm25_retriever, _chunks
    if _bm25_retriever is None and not _chunks:
        _chunks = load_bm25_from_disk()
        if _chunks:
            _bm25_retriever = BM25Retriever.from_documents(_chunks)
            _bm25_retriever.k = TOP_K * 2
    return _bm25_retriever


def rebuild_bm25_from_chroma() -> int:
    """
    启动时兜底：若 BM25 pickle 缺失，从 Chroma 全量 metadata 重建 BM25 索引。

    Returns:
        重建的 chunk 数量；失败或无数据时返回 0。
    """
    try:
        vs = get_vectorstore()
        data = vs.get()
        ids = data.get("ids", [])
        if not ids:
            return 0
        docs = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(data.get("documents", []), data.get("metadatas", []))
        ]
        set_chunks(docs)
        return len(docs)
    except Exception as e:
        logger.warning(f"BM25 rebuild from Chroma failed: {e}")
        return 0


def build_vectorstore(chunks: List[Document], force_rebuild: bool = False) -> Chroma:
    """
    用 chunk 列表构建/重建 Chroma 向量库。

    同时调用 set_chunks，保证 BM25 与向量库数据一致。

    force_rebuild=True：先 delete_collection 再写入，避免旧文档残留。
    """
    global _vectorstore
    set_chunks(chunks)
    embeddings = get_embeddings()

    if force_rebuild:
        try:
            temp = Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=embeddings,
                collection_name=COLLECTION_NAME,
            )
            temp.delete_collection()
        except Exception:
            pass  # 集合不存在时忽略

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )
    logger.info(f"VectorStore built: {len(chunks)} chunks")
    return _vectorstore


# ── 三种检索模式的具体实现 ────────────────────────────────────────────────────

def _hybrid_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """
    混合检索：BM25 + 向量，按排名融合分数后取 Top-K 候选。

    【融合逻辑】
    - 用 doc_id 或内容前 100 字符作为去重 key
    - BM25 排名贡献 0.4 权重，向量排名贡献 0.6 权重
    - 同一段被两路都命中时分数累加，体现「双路共识」

    【降级】
    - 无 BM25 chunks 时尝试从磁盘加载；仍失败则 dense only
    - embed_breaker 打开时跳过向量检索，仅 BM25
    """
    if not _chunks:
        loaded = load_bm25_from_disk()
        if loaded:
            set_chunks(loaded)
        else:
            logger.warning("No BM25 chunks, dense only")
            return _dense_retrieve(query, k)

    bm25 = get_bm25_retriever()
    bm25_docs = bm25.invoke(query) if bm25 else []

    dense_docs: List[Document] = []
    if not embed_breaker.is_open():
        try:
            dense_docs = get_vectorstore().similarity_search(query, k=k * 2)
        except Exception as e:
            logger.warning(f"Dense retrieval failed: {e}")
            embed_breaker.record_failure()

    seen: dict[str, tuple[Document, float]] = {}
    for rank, doc in enumerate(bm25_docs):
        key = doc.metadata.get("doc_id", doc.page_content[:100])
        score = 0.4 * (k * 2 - rank) / (k * 2)
        seen[key] = (doc, score) if key not in seen else (seen[key][0], seen[key][1] + score)

    for rank, doc in enumerate(dense_docs):
        key = doc.metadata.get("doc_id", doc.page_content[:100])
        score = 0.6 * (k * 2 - rank) / (k * 2)
        if key not in seen:
            seen[key] = (doc, score)
        else:
            seen[key] = (seen[key][0], seen[key][1] + score)

    merged = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in merged[:k * 2]]


def _dense_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """纯向量语义检索：适合概念型、换说法也能命中的问题。"""
    try:
        return get_vectorstore().similarity_search(query, k=k)
    except Exception as e:
        logger.error(f"Dense retrieval failed: {e}")
        return []


def _sparse_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """纯 BM25 关键词检索：适合含精确术语、型号、数字的问题。"""
    bm25 = get_bm25_retriever()
    return bm25.invoke(query) if bm25 else []


# ── Cross-Encoder 重排序 ──────────────────────────────────────────────────────

def _load_reranker():
    """
    懒加载 Cross-Encoder 模型。

    【为什么需要 Rerank】
    向量检索/BM25 是「召回」阶段，速度快但排序较粗；
    Cross-Encoder 同时看 query+doc，排序更准，但计算贵，所以只用在 Top 候选上。

    加载失败时标记为 "fallback"，降级为关键词重叠打分。
    """
    global _reranker_model
    if _reranker_model is None and RERANK_ENABLED:
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder(RERANK_MODEL)
        except Exception as e:
            logger.warning(f"Reranker load failed: {e}")
            _reranker_model = "fallback"
    return _reranker_model


def rerank_docs(docs: List[Document], query: str, top_n: Optional[int] = None) -> List[Document]:
    """
    对召回的文档列表重新排序，返回最相关的 top_n 条。

    优先 Cross-Encoder；不可用时用 query 与 doc 的词集合交集比例作为 fallback 分数。
    """
    if not docs:
        return []
    top_n = top_n or TOP_K
    reranker = _load_reranker()
    if reranker and reranker != "fallback":
        try:
            pairs = [(query, d.page_content) for d in docs]
            scores = reranker.predict(pairs)
            scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
            return [d for _, d in scored[:top_n]]
        except Exception as e:
            logger.warning(f"Rerank failed: {e}")

    # Fallback：简单关键词重叠率（零依赖兜底）
    q_tokens = set(query.lower().split())
    scored = []
    for doc in docs:
        t_tokens = set(doc.page_content.lower().split())
        score = len(q_tokens & t_tokens) / (len(q_tokens) + 1e-6)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_n]]


def retrieve_with_kg(
    query: str,
    *,
    user_roles: Optional[List[str]] = None,
    mode: Optional[str] = None,
) -> tuple[List[Document], str]:
    """
    完整检索流水线：召回 → ACL 过滤 → Rerank → 知识图谱上下文。

    【模式与降级】
    - sparse 模式：BM25 为空时 fallback dense
    - dense 模式：向量失败时 fallback sparse

    Returns:
        (文档列表, KG 上下文字符串)
    """
    retriever_mode = mode or RETRIEVAL_MODE
    if retriever_mode == "hybrid":
        docs = _hybrid_retrieve(query)
    elif retriever_mode == "sparse":
        docs = _sparse_retrieve(query)
        if not docs:
            docs = _dense_retrieve(query)
    else:
        docs = _dense_retrieve(query)
        if not docs:
            docs = _sparse_retrieve(query)

    docs = _acl_filter(docs, user_roles)
    docs = rerank_docs(docs, query, top_n=TOP_K)

    kg_context = ""
    if settings.kg_enabled:
        triples = get_kg().query(query)
        kg_context = get_kg().to_context(triples)

    return docs, kg_context


def build_retriever(mode: Optional[str] = None) -> Callable[[str], List[Document]]:
    """
    根据 RETRIEVAL_MODE 配置返回对应的检索函数。

    返回 Callable[[str], List[Document]]，便于 LangGraph 节点或单元测试 mock。
    不含 ACL/KG/rerank，仅底层召回；完整流程请用 retrieve_with_kg。
    """
    retriever_mode = mode or RETRIEVAL_MODE
    if retriever_mode == "hybrid":
        return _hybrid_retrieve
    if retriever_mode == "sparse":
        return _sparse_retrieve
    return _dense_retrieve
