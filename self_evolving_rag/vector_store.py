"""
向量存储模块
支持 ChromaDB，提供增删改查和权重更新能力
"""
import uuid
import json
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np

from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import (
    OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL, EMBEDDING_DIM,
    CHROMA_COLLECTION_NAME, VECTOR_STORE_DIR
)


class VectorStore:
    """向量数据库管理器"""

    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=OLLAMA_EMBED_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
        self._client = None
        self._collection = None
        self._init_store()

    def _init_store(self):
        """初始化向量库"""
        self._client = Chroma(
            persist_directory=str(VECTOR_STORE_DIR),
            embedding_function=self.embeddings,
            collection_name=CHROMA_COLLECTION_NAME,
        )

    @property
    def collection(self):
        return self._client

    def add_documents(
        self,
        texts: List[str],
        metadatas: List[dict],
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        添加文档到向量库
        texts: 文本列表
        metadatas: 元数据列表（必须与texts一一对应）
        ids: 可选ID列表
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        documents = []
        for text, metadata, doc_id in zip(texts, metadatas, ids):
            documents.append(Document(
                page_content=text,
                metadata=metadata,
                id=doc_id
            ))

        self._client.add_documents(documents)
        return ids

    def similarity_search_with_scores(
        self,
        query: str,
        k: int = 5,
        filter_metadata: Optional[dict] = None
    ) -> List[Tuple[Document, float]]:
        """
        带相似度分数的检索
        返回: [(Document, score), ...]  按分数降序
        """
        docs = self._client.similarity_search_with_score(
            query=query,
            k=k,
            filter=filter_metadata
        )
        # 按分数升序排序（分数越低越相似）
        return sorted(docs, key=lambda x: x[1])

    def update_chunk_score(self, chunk_id: str, score_delta: float) -> bool:
        """
        更新单个chunk的权重分（进化机制）
        score_delta: 分数变化量，正值提升优先级，负值降低
        """
        try:
            chunk = self._client.get(ids=[chunk_id])
            if chunk and chunk.get("metadatas"):
                current_score = chunk["metadatas"][0].get("boost_score", 0.0)
                new_score = current_score + score_delta
                # 将boost_score写入metadata
                self._client.update_metadata(
                    ids=[chunk_id],
                    metadata={"boost_score": new_score}
                )
                return True
        except Exception as e:
            print(f"[VectorStore] 更新chunk失败: {e}")
        return False

    def batch_update_scores(self, updates: List[dict]) -> int:
        """
        批量更新chunk分数
        updates: [{"chunk_id": str, "score_delta": float}, ...]
        """
        success = 0
        for update in updates:
            if self.update_chunk_score(update["chunk_id"], update["score_delta"]):
                success += 1
        return success

    def get_all_chunks(self, limit: int = 1000) -> List[dict]:
        """获取所有chunks用于分析"""
        try:
            result = self._client.get(limit=limit)
            return [
                {
                    "id": m.get("id", result["ids"][i]),
                    "content": result["documents"][i],
                    "metadata": m,
                    "score": m.get("boost_score", 0.0)
                }
                for i, m in enumerate(result.get("metadatas", []))
            ]
        except Exception:
            return []

    def delete_by_source(self, source: str) -> bool:
        """按来源删除文档"""
        try:
            self._client.delete(filter={"source": source})
            return True
        except Exception as e:
            print(f"[VectorStore] 删除失败: {e}")
            return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        try:
            all_data = self._client.get(limit=1)
            count = len(all_data.get("ids", []))
            if count == 0:
                # 尝试获取总数
                result = self._client.get()
                count = len(result.get("ids", []))
            return {"total_chunks": count}
        except Exception:
            return {"total_chunks": 0}

    def weighted_search(self, query: str, k: int = 5) -> List[Tuple[Document, float]]:
        """
        加权检索：结合相似度和boost_score
        进化后的检索策略
        """
        docs_with_scores = self.similarity_search_with_scores(query, k=k * 2)

        weighted_results = []
        for doc, sim_score in docs_with_scores:
            boost = doc.metadata.get("boost_score", 0.0)
            # 综合分数 = 相似度 + boost权重加成
            weighted_score = sim_score + boost
            weighted_results.append((doc, weighted_score))

        # 按加权分数降序排列
        weighted_results.sort(key=lambda x: x[1])
        return weighted_results[:k]
