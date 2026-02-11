"""
自进化引擎
核心模块：根据用户反馈自动优化检索权重、更新知识库
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

from config import (
    DATA_DIR, EVOLUTION_LOG, EVOLUTION_TRIGGER_THRESHOLD,
    POSITIVE_THRESHOLD, NEGATIVE_THRESHOLD, BOOST_WEIGHT,
    AUTO_RETRAIN_INTERVAL
)


class EvolutionEngine:
    """
    自进化引擎
    通过分析用户反馈，自动调整chunk权重，实现越用越聪明的RAG系统
    """

    def __init__(self, vector_store, feedback_collector, llm_manager):
        self.vector_store = vector_store
        self.feedback = feedback_collector
        self.llm = llm_manager
        self.evolution_log_path = Path(EVOLUTION_LOG)
        self.evolution_log = self._load_log()

    def _load_log(self) -> List[Dict]:
        """加载进化日志"""
        if self.evolution_log_path.exists():
            try:
                with open(self.evolution_log_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_log(self):
        """保存进化日志"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.evolution_log_path, "w", encoding="utf-8") as f:
            json.dump(self.evolution_log, f, ensure_ascii=False, indent=2)

    def _log_evolution(self, event_type: str, details: Dict):
        """记录进化事件"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details
        }
        self.evolution_log.append(event)
        # 只保留最近100条
        if len(self.evolution_log) > 100:
            self.evolution_log = self.evolution_log[-100:]
        self._save_log()

    def process_feedback(
        self,
        question: str,
        answer: str,
        chunk_ids: List[str],
        rating: int,
        score: float,
        correction: Optional[str] = None
    ):
        """
        处理一条反馈，实时更新权重
        rating: 1=good, -1=bad
        score: 0.0~1.0
        """
        boost_delta = 0.0

        if rating == 1 or score >= POSITIVE_THRESHOLD:
            # 好评：提升相关chunk的权重
            boost_delta = BOOST_WEIGHT
            for cid in chunk_ids:
                self.vector_store.update_chunk_score(cid, boost_delta)
            self._log_evolution("boost", {
                "question": question[:50],
                "chunk_ids": chunk_ids,
                "delta": boost_delta
            })

        elif rating == -1 or score <= NEGATIVE_THRESHOLD:
            # 差评：降低相关chunk的权重
            boost_delta = -BOOST_WEIGHT
            for cid in chunk_ids:
                self.vector_store.update_chunk_score(cid, boost_delta)
            self._log_evolution("penalize", {
                "question": question[:50],
                "chunk_ids": chunk_ids,
                "delta": boost_delta
            })

            # 如果用户提供了修正文本，尝试学习
            if correction:
                self._learn_from_correction(question, correction, chunk_ids)

    def _learn_from_correction(
        self,
        question: str,
        correction: str,
        used_chunk_ids: List[str]
    ):
        """
        从用户修正中学习
        尝试将修正内容整合到相关chunk中（标记为需要更新）
        """
        self._log_evolution("learn_correction", {
            "question": question[:50],
            "correction": correction[:100],
            "learned_from": used_chunk_ids
        })

    def trigger_evolution(self) -> Dict[str, Any]:
        """
        触发完整自进化流程
        分析近期反馈模式，批量更新chunk权重
        """
        start_time = time.time()
        updates = []

        # 1. 分析好评chunk
        good_feedback = self.feedback.get_feedback_by_rating(1)
        chunk_good_count = defaultdict(int)
        for fb in good_feedback:
            for cid in fb.get("chunk_ids", []):
                chunk_good_count[cid] += 1

        # 2. 分析差评chunk
        bad_feedback = self.feedback.get_feedback_by_rating(-1)
        chunk_bad_count = defaultdict(int)
        for fb in bad_feedback:
            for cid in fb.get("chunk_ids", []):
                chunk_bad_count[cid] += 1

        # 3. 综合评分：计算每个chunk的净得分
        all_chunks = self.vector_store.get_all_chunks()
        chunk_net_score = {}

        for chunk in all_chunks:
            cid = chunk["id"]
            good = chunk_good_count.get(cid, 0)
            bad = chunk_bad_count.get(cid, 0)
            net = good - bad
            if net != 0:
                chunk_net_score[cid] = {
                    "net": net,
                    "good": good,
                    "bad": bad,
                    "boost": net * BOOST_WEIGHT
                }

        # 4. 批量更新
        for cid, scores in chunk_net_score.items():
            if abs(scores["boost"]) >= BOOST_WEIGHT * 0.5:
                self.vector_store.update_chunk_score(cid, scores["boost"])
                updates.append({
                    "chunk_id": cid,
                    "boost": scores["boost"],
                    "good": scores["good"],
                    "bad": scores["bad"]
                })

        # 5. 找出表现最好和最差的chunk
        top_chunks = sorted(chunk_net_score.items(), key=lambda x: x[1]["net"], reverse=True)[:5]
        bottom_chunks = sorted(chunk_net_score.items(), key=lambda x: x[1]["net"])[:5]

        elapsed = time.time() - start_time
        result = {
            "elapsed_seconds": round(elapsed, 2),
            "chunks_updated": len(updates),
            "top_chunks": [{"id": c[0], **c[1]} for c in top_chunks],
            "bottom_chunks": [{"id": c[0], **c[1]} for c in bottom_chunks],
            "good_analyzed": len(good_feedback),
            "bad_analyzed": len(bad_feedback)
        }

        self._log_evolution("full_evolution", result)
        return result

    def should_auto_evolve(self) -> bool:
        """判断是否应该触发自动进化"""
        stats = self.feedback.get_stats()
        return stats["total"] > 0 and stats["total"] % AUTO_RETRAIN_INTERVAL == 0

    def get_evolution_stats(self) -> Dict[str, Any]:
        """获取进化统计数据"""
        stats = self.feedback.get_stats()
        total_events = len(self.evolution_log)

        # 分析进化趋势
        recent_events = self.evolution_log[-20:]
        boosts = sum(1 for e in recent_events if e["type"] == "boost")
        penalties = sum(1 for e in recent_events if e["type"] == "penalty" or e["type"] == "penalize")
        learnings = sum(1 for e in recent_events if e["type"] == "learn_correction")

        # 全时间段的boost/penalty
        all_boosts = sum(1 for e in self.evolution_log if e["type"] in ("boost", "full_evolution"))
        all_penalties = sum(1 for e in self.evolution_log if e["type"] in ("penalty", "penalize"))

        return {
            "feedback_stats": stats,
            "evolution_events_total": total_events,
            "recent_boosts": boosts,
            "recent_penalties": penalties,
            "recent_learnings": learnings,
            "all_time_boosts": all_boosts,
            "all_time_penalties": all_penalties,
            "last_evolution": self.evolution_log[-1] if self.evolution_log else None
        }

    def get_knowledge_gaps(self) -> List[Dict[str, Any]]:
        """
        分析知识盲点
        找出用户经常问但知识库回答不好的话题
        """
        bad_feedback = self.feedback.get_feedback_by_rating(-1)
        # 简单的关键词分析
        topics = defaultdict(int)
        for fb in bad_feedback:
            q = fb["question"].lower()
            # 简单分词
            words = q.split()
            for w in words:
                if len(w) > 2:
                    topics[w] += 1

        sorted_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)
        return [
            {"keyword": k, "frequency": v}
            for k, v in sorted_topics[:10]
        ]
