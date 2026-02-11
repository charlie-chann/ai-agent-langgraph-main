"""
反馈收集模块
收集用户对RAG回答的评价，支持 thumbs up/down、评分、修正文本
"""
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from config import FEEDBACK_DB, EVOLUTION_LOG, DATA_DIR


class FeedbackCollector:
    """用户反馈收集器"""

    def __init__(self, db_path: str = str(FEEDBACK_DB)):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化SQLite数据库"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                rating INTEGER DEFAULT 0,  -- 1=good, -1=bad, 0=neutral
                score REAL DEFAULT 0.5,    -- 0.0~1.0
                correction TEXT,           -- 用户修正文本
                comment TEXT,              -- 用户评论
                chunk_ids TEXT,            -- 使用的chunk_ids (JSON)
                used_sources TEXT,         -- 使用的来源 (JSON)
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT              -- 额外信息 (JSON)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT,
                query_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def add_feedback(
        self,
        question: str,
        answer: str,
        rating: int = 0,
        score: float = 0.5,
        correction: Optional[str] = None,
        comment: Optional[str] = None,
        chunk_ids: Optional[List[str]] = None,
        used_sources: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """添加一条反馈"""
        fid = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute("""
            INSERT INTO feedback 
            (id, session_id, question, answer, rating, score, correction, comment, chunk_ids, used_sources, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fid,
            session_id,
            question,
            answer,
            rating,
            score,
            correction,
            comment,
            json.dumps(chunk_ids or [], ensure_ascii=False),
            json.dumps(used_sources or [], ensure_ascii=False),
            json.dumps(metadata or {}, ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
        return fid

    def get_recent_feedback(self, limit: int = 20) -> List[Dict]:
        """获取最近的反馈"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT id, question, answer, rating, score, correction, comment, created_at
            FROM feedback 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "question": r[1], "answer": r[2],
                "rating": r[3], "score": r[4], "correction": r[5],
                "comment": r[6], "created_at": r[7]
            }
            for r in rows
        ]

    def get_feedback_by_rating(self, rating: int) -> List[Dict]:
        """按评分获取反馈"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT id, question, answer, score, chunk_ids, correction
            FROM feedback 
            WHERE rating = ?
            ORDER BY created_at DESC
        """, (rating,))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "question": r[1], "answer": r[2],
                "score": r[3], "chunk_ids": json.loads(r[4]), "correction": r[5]
            }
            for r in rows
        ]

    def get_pending_eviction_data(self, min_score: float = 0.3, max_score: float = 0.7) -> List[Dict]:
        """获取需要进化的反馈数据（中性反馈）"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            SELECT id, question, answer, chunk_ids, used_sources
            FROM feedback 
            WHERE score BETWEEN ? AND ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (min_score, max_score))
        rows = c.fetchall()
        conn.close()
        return [
            {
                "id": r[0], "question": r[1], "answer": r[2],
                "chunk_ids": json.loads(r[3]), "used_sources": json.loads(r[4])
            }
            for r in rows
        ]

    def get_stats(self) -> Dict[str, Any]:
        """获取反馈统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*), AVG(score) FROM feedback")
        total_count, avg_score = c.fetchone()

        c.execute("SELECT COUNT(*) FROM feedback WHERE rating = 1")
        good_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM feedback WHERE rating = -1")
        bad_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM feedback WHERE correction IS NOT NULL AND correction != ''")
        corrected = c.fetchone()[0]

        conn.close()
        return {
            "total": total_count or 0,
            "avg_score": round(avg_score, 3) if avg_score else 0,
            "good": good_count or 0,
            "bad": bad_count or 0,
            "corrected": corrected or 0
        }

    def update_session(self, session_id: str):
        """更新会话活跃时间"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute("""
            INSERT INTO sessions (session_id, last_active, query_count)
            VALUES (?, ?, 1)
            ON CONFLICT(session_id) DO UPDATE SET
            last_active = ?, query_count = query_count + 1
        """, (session_id, now, now))
        conn.commit()
        conn.close()

    def clear_all(self) -> bool:
        """清空所有反馈（谨慎使用）"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM feedback")
        conn.commit()
        conn.close()
        return True
