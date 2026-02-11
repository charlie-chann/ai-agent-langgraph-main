"""
tools/retriever.py — 混合检索 + 重排序

【职责】
1. 管理 ChromaDB 向量库（持久化，语义检索）
2. 管理 BM25 内存索引（关键词检索）
3. 融合两种检索结果（Hybrid Search）
4. Cross-Encoder 精排，提升 Top-K 质量

【设计原因】
1. 单例缓存 _vectorstore：避免每次问答重复连接 Chroma、重复加载 embedding 模型
2. Hybrid：向量擅长「语义相近」，BM25 擅长「专有名词/数字精确匹配」，互补
3. 分数融合 0.4(BM25) + 0.6(向量)：向量权重略高，符合语义 RAG 主流实践
4. Rerank 在召回之后：先用便宜的方法捞候选，再用 Cross-Encoder 精排，平衡速度与质量
"""
from typing import List, Optional, Callable
from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.retrievers import BM25Retriever
from loguru import logger

from config import (
    settings,
    OLLAMA_BASE_URL,
    EMBEDDING_MODEL,
    CHROMA_DIR,
    COLLECTION_NAME,
    TOP_K,
    RETRIEVAL_MODE,
    RERANK_ENABLED,
    RERANK_MODEL,
)


# ── 进程级全局缓存 ────────────────────────────────────────────────────────────
# 注意：BM25 索引只在内存中，进程重启后需重新 ingest 才能恢复 BM25；
#       ChromaDB 数据在 chroma_db/ 目录，重启后仍可加载。
_vectorstore: Optional[Chroma] = None
_bm25_retriever: Optional[BM25Retriever] = None
_chunks: List[Document] = []  # BM25 需要的原始 chunk 列表


def get_vectorstore(force_reload: bool = False) -> Chroma:
    """
    获取 Chroma 向量库单例。

    首次调用时连接本地 chroma_db/ 目录；若目录不存在会在首次 ingest 时创建。
    embedding 使用 Ollama 的 nomic-embed-text，与主 LLM 分离。
    """
    global _vectorstore
    if _vectorstore is None or force_reload:
        embeddings = OllamaEmbeddings(
            model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        _vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
        )
        logger.info(f"VectorStore loaded from {CHROMA_DIR}")
    return _vectorstore


def get_bm25_retriever() -> Optional[BM25Retriever]:
    """
    获取 BM25 检索器。依赖 _chunks 已在 ingest 时通过 set_chunks 填充。

    若 _chunks 为空（例如只加载了 Chroma 但未 ingest 本次会话），返回 None。
    """
    global _bm25_retriever, _chunks
    if _bm25_retriever is None and _chunks:
        _bm25_retriever = BM25Retriever.from_documents(_chunks)
        _bm25_retriever.k = TOP_K
        logger.info(f"BM25 retriever built with {len(_chunks)} chunks")
    return _bm25_retriever


def set_chunks(chunks: List[Document]) -> None:
    """
    更新 BM25 使用的 chunk 列表，并重建 BM25 索引。

    每次 ingest 新文档时必须调用，否则 hybrid 模式的 BM25 部分为空。
    """
    global _chunks, _bm25_retriever
    _chunks = chunks
    _bm25_retriever = BM25Retriever.from_documents(chunks)
    _bm25_retriever.k = TOP_K
    logger.info(f"Chunks updated: {len(chunks)} documents")


def build_vectorstore(chunks: List[Document], force_rebuild: bool = False) -> Chroma:
    """
    用 chunk 列表构建/重建 Chroma 向量库。

    同时调用 set_chunks，保证 BM25 与向量库数据一致。

    force_rebuild=True：先 delete_collection 再写入，避免旧文档残留。
    """
    global _vectorstore

    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )

    # 同步更新 BM25 内存索引
    set_chunks(chunks)

    if force_rebuild:
        try:
            temp_vs = Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=embeddings,
                collection_name=COLLECTION_NAME,
            )
            temp_vs.delete_collection()
            logger.info("Deleted existing collection")
        except Exception:
            pass  # 集合不存在时忽略

    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )
    logger.info(f"VectorStore built with {len(chunks)} chunks → {CHROMA_DIR}")
    return _vectorstore


def load_vectorstore() -> Chroma:
    """向后兼容别名，等价于 get_vectorstore()。"""
    return get_vectorstore()


# ── 三种检索模式的具体实现 ────────────────────────────────────────────────────

def _hybrid_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """
    混合检索：BM25 + 向量，按排名融合分数后取 Top-K。

    【融合逻辑】
    - 用 chunk 内容前 100 字符作为去重 key（同一文档可能被两路都召回）
    - BM25 排名贡献 0.4 权重，向量排名贡献 0.6 权重
    - 同一段被两路都命中时分数累加，体现「双路共识」
    """
    global _chunks

    if not _chunks:
        logger.warning("No chunks loaded, falling back to dense only")
        return _dense_retrieve(query, k)

    bm25 = get_bm25_retriever()
    bm25_docs = bm25.invoke(query) if bm25 else []

    try:
        vs = get_vectorstore()
        dense_docs = vs.similarity_search(query, k=k)
    except Exception as e:
        logger.warning(f"Dense retrieval failed: {e}")
        dense_docs = []

    seen: dict[str, tuple[Document, float]] = {}

    for rank, doc in enumerate(bm25_docs):
        key = doc.page_content[:100]
        score = 0.4 * (k - rank) / k  # 排名越靠前分数越高
        if key not in seen:
            seen[key] = (doc, score)
        else:
            seen[key] = (seen[key][0], seen[key][1] + score)

    for rank, doc in enumerate(dense_docs):
        key = doc.page_content[:100]
        score = 0.6 * (k - rank) / k
        if key not in seen:
            seen[key] = (doc, score)
        else:
            seen[key] = (seen[key][0], seen[key][1] + score)

    merged = sorted(seen.values(), key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in merged[:k]]


def _dense_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """纯向量语义检索：适合概念型、换说法也能命中的问题。"""
    try:
        vs = get_vectorstore()
        return vs.similarity_search(query, k=k)
    except Exception as e:
        logger.error(f"Dense retrieval failed: {e}")
        return []


def _sparse_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """纯 BM25 关键词检索：适合含精确术语、型号、数字的问题。"""
    bm25 = get_bm25_retriever()
    if bm25 is None:
        logger.warning("BM25 not initialized, returning empty")
        return []
    return bm25.invoke(query)


def build_retriever(
    chunks: Optional[List[Document]] = None,
    vectorstore: Optional[Chroma] = None,
    mode: Optional[str] = None
) -> Callable:
    """
    根据 RETRIEVAL_MODE 配置返回对应的检索函数。

    返回的是 Callable[[str], List[Document]]，agent 直接调用 retriever_fn(query)。

    设计为返回函数而非对象：与 LangGraph 节点解耦，便于单元测试 mock。
    """
    global _chunks

    if chunks is not None:
        set_chunks(chunks)

    retriever_mode = mode or RETRIEVAL_MODE

    if retriever_mode == "hybrid":
        logger.info("Using hybrid retriever (BM25 + vector)")
        return _hybrid_retrieve
    elif retriever_mode == "sparse":
        logger.info("Using sparse retriever (BM25 only)")
        return _sparse_retrieve
    else:
        logger.info("Using dense retriever (vector only)")
        return _dense_retrieve


# ── Cross-Encoder 重排序 ──────────────────────────────────────────────────────
_reranker_model = None  # 懒加载，首次 rerank 时才下载/加载模型


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
            logger.info(f"Loaded cross-encoder reranker: {RERANK_MODEL}")
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}. Using keyword overlap rerank.")
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
            pairs = [(query, doc.page_content) for doc in docs]
            scores = reranker.predict(pairs)
            scored_docs = list(zip(scores, docs))
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            reranked = [doc for _, doc in scored_docs[:top_n]]
            logger.debug(f"Cross-encoder reranked {len(docs)} → {len(reranked)} docs")
            return reranked
        except Exception as e:
            logger.warning(f"Cross-encoder rerank failed: {e}")

    # Fallback：简单关键词重叠率（零依赖兜底）
    query_tokens = set(query.lower().split())
    scored = []
    for doc in docs:
        text_tokens = set(doc.page_content.lower().split())
        score = len(query_tokens & text_tokens) / (len(query_tokens) + 1e-6)
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    reranked = [d for _, d in scored[:top_n]]
    logger.debug(f"Keyword reranked {len(docs)} → {len(reranked)} docs")
    return reranked
