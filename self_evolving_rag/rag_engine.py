"""
Self-Evolving RAG 核心引擎
整合：检索 + 生成 + 反馈 + 进化
"""
import time
import uuid
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime

from vector_store import VectorStore
from llm import LLManager
from document_processor import DocumentProcessor
from feedback import FeedbackCollector
from evolution import EvolutionEngine
from config import DEFAULT_TOP_K, MAX_CONTEXT_CHUNKS, SIMILARITY_THRESHOLD


class SelfEvolvingRAG:
    """
    自进化RAG系统主类
    对外提供简洁的接口，内部协调各模块工作
    """

    def __init__(self):
        print("[RAG] 初始化自进化RAG系统...")
        self.vector_store = VectorStore()
        self.doc_processor = DocumentProcessor()
        self.llm = LLManager()
        self.feedback = FeedbackCollector()
        self.evolution = EvolutionEngine(
            self.vector_store,
            self.feedback,
            self.llm
        )
        self.session_id = str(uuid.uuid4())
        self._conversation_history = []
        print("[RAG] 初始化完成 ✓")

    # ============ 文档管理 ============

    def ingest_file(self, file_path: str) -> Dict[str, Any]:
        """ ingestion: 导入单个文件到知识库"""
        try:
            chunks, metadatas = self.doc_processor.process_file(file_path)
            ids = self.vector_store.add_documents(chunks, metadatas)
            return {
                "ok": True,
                "file": file_path,
                "chunks": len(chunks),
                "chunk_ids": ids
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ingest_folder(self, folder_path: str, recursive: bool = True) -> Dict[str, Any]:
        """批量导入文件夹"""
        try:
            chunks, metadatas = self.doc_processor.process_folder(folder_path, recursive)
            if not chunks:
                return {"ok": False, "error": "未找到有效文档"}
            ids = self.vector_store.add_documents(chunks, metadatas)
            return {
                "ok": True,
                "folder": folder_path,
                "chunks": len(chunks),
                "chunk_ids": ids[:5],  # 只返回前5个ID示例
                "truncated": len(ids) > 5
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ingest_text(self, text: str, source_name: str = "manual_input") -> Dict[str, Any]:
        """直接写入文本片段"""
        chunks, metadatas = self.doc_processor.process_file.__self__.chunk_text(text)
        # 自定义metadatas
        metadatas = [{
            "source": source_name,
            "source_path": "manual",
            "boost_score": 0.0,
            "hit_count": 0,
            "created_at": datetime.now().isoformat(),
            "doc_id": hashlib.md5(f"{source_name}_{i}".encode()).hexdigest()[:12]
        } for i in range(len(chunks))]
        ids = self.vector_store.add_documents(chunks, metadatas)
        return {"ok": True, "chunks": len(chunks), "chunk_ids": ids}

    def delete_source(self, source_name: str) -> Dict[str, Any]:
        """按来源删除文档"""
        ok = self.vector_store.delete_by_source(source_name)
        return {"ok": ok, "deleted": source_name}

    # ============ 问答 ============

    def ask(
        self,
        question: str,
        top_k: int = DEFAULT_TOP_K,
        use_evolution: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        核心问答接口
        use_evolution: 是否使用加权检索（进化后的智能检索）
        """
        start = time.time()

        # 更新会话
        self.feedback.update_session(session_id or self.session_id)

        # 检索
        if use_evolution:
            retrieved = self.vector_store.weighted_search(question, k=top_k)
        else:
            retrieved = self.vector_store.similarity_search_with_scores(question, k=top_k)

        # 过滤低相似度
        retrieved = [
            (doc, score) for doc, score in retrieved
            if score < (1 - SIMILARITY_THRESHOLD) or score > SIMILARITY_THRESHOLD
        ]

        # 更新命中次数
        chunk_ids = [doc.id for doc, _ in retrieved]
        for cid in chunk_ids:
            self.vector_store.update_chunk_score(cid, 0.001)  # 轻微加分

        # 生成回答
        result = self.llm.rag_answer(question, retrieved, use_weighted=use_evolution)

        elapsed = time.time() - start

        # 保存对话历史
        entry = {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "chunk_ids": chunk_ids,
            "elapsed": round(elapsed, 2),
            "timestamp": datetime.now().isoformat()
        }
        self._conversation_history.append(entry)

        # 触发自动进化检查
        if self.evolution.should_auto_evolve():
            self.evolution.trigger_evolution()

        return {
            "ok": True,
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "chunk_ids": chunk_ids,
            "elapsed_seconds": round(elapsed, 2),
            "model": result.get("model", "unknown"),
            "session_id": session_id or self.session_id,
            "evolution_active": use_evolution
        }

    def submit_feedback(
        self,
        question: str,
        answer: str,
        chunk_ids: List[str],
        rating: int,
        score: float = 0.5,
        correction: Optional[str] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """提交用户反馈"""
        fid = self.feedback.add_feedback(
            question=question,
            answer=answer,
            rating=rating,
            score=score,
            correction=correction,
            comment=comment,
            chunk_ids=chunk_ids,
            session_id=self.session_id
        )

        # 实时处理反馈
        self.evolution.process_feedback(
            question=question,
            answer=answer,
            chunk_ids=chunk_ids,
            rating=rating,
            score=score,
            correction=correction
        )

        return {
            "ok": True,
            "feedback_id": fid,
            "message": "感谢您的反馈！系统已记录并开始学习。"
        }

    # ============ 统计信息 ============

    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        store_stats = self.vector_store.get_stats()
        feedback_stats = self.feedback.get_stats()
        evolution_stats = self.evolution.get_evolution_stats()
        model_info = self.llm.get_model_info()

        return {
            "vector_store": store_stats,
            "feedback": feedback_stats,
            "evolution": evolution_stats,
            "model": model_info,
            "session_id": self.session_id,
            "conversation_count": len(self._conversation_history)
        }

    def get_recent_history(self, limit: int = 10) -> List[Dict]:
        """获取最近的问答历史"""
        return self._conversation_history[-limit:]

    def clear_history(self):
        """清空对话历史"""
        self._conversation_history = []
