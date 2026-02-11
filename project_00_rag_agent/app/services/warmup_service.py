"""启动预热：BM25 等检索依赖。"""
from __future__ import annotations

from loguru import logger

from app.retrieval.retriever import rebuild_bm25_from_chroma


def warmup() -> int:
    """
    应用启动时调用：从 Chroma 重建 BM25 稀疏索引（若 pickle 缺失或需同步）。

    保证 hybrid/sparse 检索模式在 API 启动后立即可用。
    """
    n = rebuild_bm25_from_chroma()
    logger.info(f"Startup: rebuilt BM25 with {n} chunks")
    return n
