# tools/candidate_db.py — In-memory candidate database with CRUD operations
"""
候选人数据库工具（内存版，可替换为真实数据库）。
支持：增删查改候选人档案、状态流转、搜索过滤。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from loguru import logger

from config import CANDIDATES_DB_PATH

# In-memory store
_CANDIDATES: dict[str, dict] = {}

VALID_STATUSES = {"submitted", "screening", "shortlisted", "interview", "offer", "rejected", "withdrawn"}


def _new_id() -> str:
    return f"C{str(uuid.uuid4())[:6].upper()}"


def _now() -> int:
    return int(time.time())


@tool
def add_candidate(
    name: str,
    email: str,
    position: str,
    skills: str,
    years_experience: int = 0,
    education: str = "本科",
    resume_text: str = "",
) -> str:
    """添加候选人到数据库。
    Args:
        name: 候选人姓名
        email: 联系邮箱
        position: 应聘职位
        skills: 技能列表（逗号分隔，如 "Python,LangChain,AWS"）
        years_experience: 工作年限
        education: 最高学历（高中/大专/本科/硕士/博士）
        resume_text: 简历全文（可选，用于关键词搜索）
    Returns: 候选人ID确认信息
    """
    # Input validation
    name = name.strip()[:100]
    email = email.strip()[:200]
    if "@" not in email or len(email) < 5:
        return f"❌ 邮箱格式无效: {email!r}"
    position = position.strip()[:200]
    if not name or not position:
        return "❌ 姓名和职位不能为空"
    years_experience = max(0, min(int(years_experience), 50))
    skills_list = [s.strip() for s in skills.split(",") if s.strip()][:30]

    cid = _new_id()
    _CANDIDATES[cid] = {
        "id": cid,
        "name": name,
        "email": email,
        "position": position,
        "skills": skills_list,
        "years_experience": years_experience,
        "education": education[:50],
        "resume_text": resume_text[:5000],
        "status": "submitted",
        "score": None,
        "notes": [],
        "created_at": _now(),
        "updated_at": _now(),
        "job_count": max(1, years_experience // 2),  # Estimate job count
    }
    logger.info(f"[add_candidate] {name} → {cid}, position: {position}")
    return f"✅ 候选人已添加\nID: {cid}\n姓名: {name}\n职位: {position}\n状态: submitted"


@tool
def get_candidate(candidate_id: str) -> str:
    """通过ID查询候选人详情。
    Args:
        candidate_id: 候选人ID（如 C1A2B3）
    Returns: 候选人详细信息（JSON格式）
    """
    cid = candidate_id.strip().upper()
    candidate = _CANDIDATES.get(cid)
    if not candidate:
        return f"❌ 未找到候选人: {cid}"
    return json.dumps(candidate, ensure_ascii=False, indent=2)


@tool
def update_candidate_status(candidate_id: str, status: str, note: str = "") -> str:
    """更新候选人状态。
    Args:
        candidate_id: 候选人ID
        status: 新状态（submitted/screening/shortlisted/interview/offer/rejected/withdrawn）
        note: 备注说明（可选）
    Returns: 更新结果
    """
    cid = candidate_id.strip().upper()
    status = status.lower().strip()
    if status not in VALID_STATUSES:
        return f"❌ 无效状态: {status!r}，允许值: {', '.join(sorted(VALID_STATUSES))}"
    candidate = _CANDIDATES.get(cid)
    if not candidate:
        return f"❌ 未找到候选人: {cid}"

    old_status = candidate["status"]
    candidate["status"] = status
    candidate["updated_at"] = _now()
    if note:
        candidate["notes"].append(f"[{status}] {note.strip()[:500]}")

    logger.info(f"[update_status] {cid}: {old_status} → {status}")
    return f"✅ {candidate['name']} 状态已更新: {old_status} → {status}"


@tool
def list_candidates(position: str = "", status: str = "", limit: int = 20) -> str:
    """列出候选人列表，支持按职位和状态过滤。
    Args:
        position: 过滤职位（空则不过滤）
        status: 过滤状态（空则不过滤）
        limit: 最大返回数量（1-50）
    Returns: 候选人摘要列表（JSON格式）
    """
    limit = max(1, min(limit, 50))
    candidates = list(_CANDIDATES.values())
    if position:
        candidates = [c for c in candidates if position.lower() in c["position"].lower()]
    if status:
        candidates = [c for c in candidates if c["status"] == status.lower()]

    # Sort by score descending, then by created_at
    candidates.sort(key=lambda c: (c.get("score") or 0, c["created_at"]), reverse=True)
    candidates = candidates[:limit]

    if not candidates:
        return json.dumps({"found": False, "message": "没有符合条件的候选人"}, ensure_ascii=False)

    summary = [
        {
            "id": c["id"],
            "name": c["name"],
            "position": c["position"],
            "status": c["status"],
            "score": c.get("score"),
            "education": c["education"],
            "years_experience": c["years_experience"],
        }
        for c in candidates
    ]
    return json.dumps({"found": True, "count": len(summary), "candidates": summary}, ensure_ascii=False, indent=2)


@tool
def set_candidate_score(candidate_id: str, score: float, decision: str) -> str:
    """记录候选人的筛选评分结果。
    Args:
        candidate_id: 候选人ID
        score: 综合评分（0.0 ~ 1.0）
        decision: 决策（shortlist/review/reject）
    Returns: 记录结果
    """
    cid = candidate_id.strip().upper()
    candidate = _CANDIDATES.get(cid)
    if not candidate:
        return f"❌ 未找到候选人: {cid}"
    score = max(0.0, min(float(score), 1.0))
    candidate["score"] = round(score, 3)
    candidate["updated_at"] = _now()
    logger.info(f"[set_score] {cid}: score={score:.3f}, decision={decision}")
    return f"✅ {candidate['name']} 评分已记录: {score:.2f} ({decision})"


def get_all_candidates() -> list[dict]:
    """Return all candidates (internal use)."""
    return list(_CANDIDATES.values())
