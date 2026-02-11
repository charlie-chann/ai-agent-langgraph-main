# tools/retriever.py — hybrid BM25 + vector retriever with cross-encoder rerank (v2.0)
from typing import List, Optional, Callable
from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
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


# ── Global Cache ──────────────────────────────────────────────────────────────
_vectorstore: Optional[Chroma] = None
_bm25_retriever: Optional[BM25Retriever] = None
_chunks: List[Document] = []  # Keep chunks in memory for BM25


def get_vectorstore(force_reload: bool = False) -> Chroma:
    """Get or create the vectorstore singleton."""
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
    """Get or create BM25 retriever (requires chunks)."""
    global _bm25_retriever, _chunks
    if _bm25_retriever is None and _chunks:
        _bm25_retriever = BM25Retriever.from_documents(_chunks)
        _bm25_retriever.k = TOP_K
        logger.info(f"BM25 retriever built with {len(_chunks)} chunks")
    return _bm25_retriever


def set_chunks(chunks: List[Document]) -> None:
    """Set chunks for BM25 retriever and rebuild."""
    global _chunks, _bm25_retriever
    _chunks = chunks
    _bm25_retriever = BM25Retriever.from_documents(chunks)
    _bm25_retriever.k = TOP_K
    logger.info(f"Chunks updated: {len(chunks)} documents")


# ── Build VectorStore ─────────────────────────────────────────────────────────
def build_vectorstore(chunks: List[Document], force_rebuild: bool = False) -> Chroma:
    """Build vectorstore from chunks."""
    global _vectorstore
    
    embeddings = OllamaEmbeddings(
        model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    
    # Save chunks for BM25
    set_chunks(chunks)
    
    if force_rebuild:
        # Delete existing collection
        try:
            temp_vs = Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=embeddings,
                collection_name=COLLECTION_NAME,
            )
            temp_vs.delete_collection()
            logger.info("Deleted existing collection")
        except Exception:
            pass
    
    _vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )
    logger.info(f"VectorStore built with {len(chunks)} chunks → {CHROMA_DIR}")
    return _vectorstore


def load_vectorstore() -> Chroma:
    """Load existing vectorstore (alias for backward compatibility)."""
    return get_vectorstore()


# ── Hybrid Retrieval ──────────────────────────────────────────────────────────
def _hybrid_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """Hybrid: merge BM25 sparse + ChromaDB dense results."""
    global _chunks
    
    if not _chunks:
        logger.warning("No chunks loaded, falling back to dense only")
        return _dense_retrieve(query, k)
    
    # Sparse BM25
    bm25 = get_bm25_retriever()
    bm25_docs = bm25.invoke(query) if bm25 else []
    
    # Dense vector
    try:
        vs = get_vectorstore()
        dense_docs = vs.similarity_search(query, k=k)
    except Exception as e:
        logger.warning(f"Dense retrieval failed: {e}")
        dense_docs = []
    
    # Merge with score fusion
    seen: dict[str, tuple[Document, float]] = {}
    for rank, doc in enumerate(bm25_docs):
        key = doc.page_content[:100]
        score = 0.4 * (k - rank) / k
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
    """Dense vector retrieval only."""
    try:
        vs = get_vectorstore()
        return vs.similarity_search(query, k=k)
    except Exception as e:
        logger.error(f"Dense retrieval failed: {e}")
        return []


def _sparse_retrieve(query: str, k: int = TOP_K) -> List[Document]:
    """Sparse BM25 retrieval only."""
    bm25 = get_bm25_retriever()
    if bm25 is None:
        logger.warning("BM25 not initialized, returning empty")
        return []
    return bm25.invoke(query)


# ── Build Retriever ───────────────────────────────────────────────────────────
def build_retriever(
    chunks: Optional[List[Document]] = None,
    vectorstore: Optional[Chroma] = None,
    mode: Optional[str] = None
) -> Callable:
    """Build a retriever based on configured mode."""
    global _chunks
    
    # Update chunks if provided
    if chunks is not None:
        set_chunks(chunks)
    
    # Determine mode
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


# ── Cross-Encoder Reranker ────────────────────────────────────────────────────
_reranker_model = None


def _load_reranker():
    """Lazy load cross-encoder reranker model."""
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
    """Rerank documents using cross-encoder or keyword overlap."""
    if not docs:
        return []
    
    top_n = top_n or TOP_K
    
    # Try cross-encoder first
    reranker = _load_reranker()
    
    if reranker and reranker != "fallback":
        try:
            # Cross-encoder scoring
            pairs = [(query, doc.page_content) for doc in docs]
            scores = reranker.predict(pairs)
            scored_docs = list(zip(scores, docs))
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            reranked = [doc for _, doc in scored_docs[:top_n]]
            logger.debug(f"Cross-encoder reranked {len(docs)} → {len(reranked)} docs")
            return reranked
        except Exception as e:
            logger.warning(f"Cross-encoder rerank failed: {e}")
    
    # Fallback: keyword overlap
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
