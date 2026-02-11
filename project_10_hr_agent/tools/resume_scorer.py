# tools/resume_scorer.py — Rule-based + keyword resume scoring tool
"""
简历评分工具：基于岗位要求，对简历进行多维度评估。
评分维度：
1. 技能匹配度（keywords）
2. 工作年限匹配
3. 学历匹配
4. 工作稳定性（跳槽频率）

总分 0.0 ~ 1.0，>= 0.65 入围，<= 0.35 淘汰
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from config import SCORE_THRESHOLD_SHORTLIST, SCORE_THRESHOLD_REJECT, RESUME_MAX_CHARS

# ── Education Level Mapping ──────────────────────────────────────────────────
_EDU_RANK = {
    "博士": 5, "phd": 5, "doctorate": 5,
    "硕士": 4, "master": 4, "mba": 4,
    "本科": 3, "bachelor": 3, "undergraduate": 3,
    "大专": 2, "associate": 2, "college": 2,
    "高中": 1, "high school": 1,
}


def _edu_rank(edu: str) -> int:
    edu_lower = edu.lower()
    for key, rank in _EDU_RANK.items():
        if key in edu_lower:
            return rank
    return 0


@dataclass
class ScoringResult:
    candidate_id: str
    candidate_name: str
    total_score: float          # 0.0 ~ 1.0
    decision: str               # shortlist | review | reject
    skill_score: float
    experience_score: float
    education_score: float
    stability_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "total_score": round(self.total_score, 3),
            "decision": self.decision,
            "skill_score": round(self.skill_score, 3),
            "experience_score": round(self.experience_score, 3),
            "education_score": round(self.education_score, 3),
            "stability_score": round(self.stability_score, 3),
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "notes": self.notes,
        }


@dataclass
class JobRequirement:
    title: str
    required_skills: list[str]       # e.g. ["Python", "LangChain", "AWS"]
    preferred_skills: list[str] = field(default_factory=list)
    min_years_exp: int = 0
    preferred_years_exp: int = 3
    min_education: str = "本科"       # 高中 | 大专 | 本科 | 硕士 | 博士
    max_job_changes: int = 5          # 5 years / N jumps → stability


def score_resume(resume: dict, job: JobRequirement) -> ScoringResult:
    """
    Score a resume against job requirements.

    resume dict expected keys:
      id, name, skills (list[str]), years_experience (int),
      education (str), job_count (int), raw_text (str, optional)
    """
    # Input sanitization
    candidate_id = str(resume.get("id", "unknown"))[:50]
    candidate_name = str(resume.get("name", "未知候选人"))[:100]
    skills = [str(s)[:100] for s in resume.get("skills", []) if s][:50]
    years_exp = max(0, min(int(resume.get("years_experience", 0)), 50))
    education = str(resume.get("education", ""))[:50]
    job_count = max(0, min(int(resume.get("job_count", 1)), 20))  # number of jobs in career
    raw_text = str(resume.get("raw_text", ""))[:RESUME_MAX_CHARS]

    notes = []

    # 1. Skill matching (weight 0.5)
    skills_lower = {s.lower() for s in skills}
    raw_lower = raw_text.lower()

    def _skill_present(skill: str) -> bool:
        return skill.lower() in skills_lower or skill.lower() in raw_lower

    matched = [s for s in job.required_skills if _skill_present(s)]
    missing = [s for s in job.required_skills if not _skill_present(s)]
    pref_matched = [s for s in job.preferred_skills if _skill_present(s)]

    req_count = len(job.required_skills)
    if req_count == 0:
        skill_score = 1.0
    else:
        base_skill = len(matched) / req_count
        bonus = len(pref_matched) / max(len(job.preferred_skills), 1) * 0.2
        skill_score = min(base_skill + bonus, 1.0)

    if missing:
        notes.append(f"缺少技能: {', '.join(missing[:5])}")

    # 2. Experience score (weight 0.25)
    if years_exp >= job.preferred_years_exp:
        exp_score = 1.0
    elif years_exp >= job.min_years_exp:
        span = max(job.preferred_years_exp - job.min_years_exp, 1)
        exp_score = 0.5 + 0.5 * (years_exp - job.min_years_exp) / span
    else:
        exp_score = max(0.0, years_exp / max(job.min_years_exp, 1) * 0.5)
        notes.append(f"工作经验不足 (需{job.min_years_exp}年，实际{years_exp}年)")

    # 3. Education score (weight 0.15)
    required_rank = _edu_rank(job.min_education)
    candidate_rank = _edu_rank(education)
    if candidate_rank >= required_rank:
        edu_score = 1.0
    elif candidate_rank == required_rank - 1:
        edu_score = 0.5
        notes.append(f"学历略低于要求 ({education} vs {job.min_education})")
    else:
        edu_score = 0.0
        notes.append(f"学历不符合要求 ({education} vs {job.min_education})")

    # 4. Stability score (weight 0.1)
    # job_count within expected years: calculate average tenure
    if years_exp > 0:
        avg_tenure = years_exp / max(job_count, 1)
        if avg_tenure >= 2.0:
            stability_score = 1.0
        elif avg_tenure >= 1.0:
            stability_score = 0.7
        else:
            stability_score = 0.3
            notes.append(f"频繁换工作（平均每{avg_tenure:.1f}年换一次）")
    else:
        stability_score = 0.8  # New graduates get neutral score

    # Weighted total
    total = (
        skill_score * 0.50 +
        exp_score * 0.25 +
        edu_score * 0.15 +
        stability_score * 0.10
    )

    # Decision
    if total >= SCORE_THRESHOLD_SHORTLIST:
        decision = "shortlist"
    elif total <= SCORE_THRESHOLD_REJECT:
        decision = "reject"
    else:
        decision = "review"

    result = ScoringResult(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        total_score=total,
        decision=decision,
        skill_score=skill_score,
        experience_score=exp_score,
        education_score=edu_score,
        stability_score=stability_score,
        matched_skills=matched,
        missing_skills=missing,
        notes=notes,
    )
    logger.info(f"[score_resume] {candidate_name}: {total:.2f} → {decision}")
    return result


def batch_score(resumes: list[dict], job: JobRequirement) -> list[ScoringResult]:
    """Score multiple resumes and return sorted by score descending."""
    results = [score_resume(r, job) for r in resumes]
    results.sort(key=lambda x: x.total_score, reverse=True)
    return results
