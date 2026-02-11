# tests/test_agent.py — project_10_hr_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest


# ── Resume Scorer Tests ────────────────────────────────────────────────────────
class TestResumeScorer:
    def setup_method(self):
        from tools.resume_scorer import JobRequirement, score_resume, ScoringResult
        self.JobRequirement = JobRequirement
        self.score_resume = score_resume
        self.ScoringResult = ScoringResult

        self.job = JobRequirement(
            title="Python Engineer",
            required_skills=["Python", "FastAPI", "PostgreSQL"],
            preferred_skills=["Docker", "AWS"],
            min_years_exp=2,
            preferred_years_exp=5,
            min_education="本科",
        )

    def _make_resume(self, **kwargs) -> dict:
        base = {
            "id": "R001",
            "name": "Test Candidate",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "years_experience": 5,
            "education": "本科",
            "job_count": 2,
        }
        base.update(kwargs)
        return base

    def test_perfect_match_gets_high_score(self):
        resume = self._make_resume(
            skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
            years_experience=6,
            education="硕士",
            job_count=2,
        )
        result = self.score_resume(resume, self.job)
        assert result.total_score >= 0.65
        assert result.decision == "shortlist"

    def test_all_skills_matched(self):
        resume = self._make_resume(skills=["Python", "FastAPI", "PostgreSQL"])
        result = self.score_resume(resume, self.job)
        assert result.skill_score == pytest.approx(1.0, abs=0.01)
        assert len(result.matched_skills) == 3
        assert len(result.missing_skills) == 0

    def test_no_skills_matched(self):
        resume = self._make_resume(skills=["Java", "Spring"])
        result = self.score_resume(resume, self.job)
        assert result.skill_score == 0.0
        assert len(result.missing_skills) == 3

    def test_partial_skill_match(self):
        resume = self._make_resume(skills=["Python"])
        result = self.score_resume(resume, self.job)
        assert 0.0 < result.skill_score < 1.0
        assert "Python" in result.matched_skills
        assert "FastAPI" in result.missing_skills

    def test_understyear_experience_lowers_score(self):
        resume = self._make_resume(years_experience=0)
        result = self.score_resume(resume, self.job)
        assert result.experience_score < 0.5

    def test_education_below_requirement_penalized(self):
        resume = self._make_resume(education="高中")
        result = self.score_resume(resume, self.job)
        assert result.education_score == 0.0

    def test_frequent_job_changes_lowers_stability(self):
        # 2 years exp, 4 jobs = 0.5 years avg tenure
        resume = self._make_resume(years_experience=2, job_count=4)
        result = self.score_resume(resume, self.job)
        assert result.stability_score < 0.7

    def test_decision_reject_for_poor_match(self):
        resume = self._make_resume(
            skills=["Java"],
            years_experience=0,
            education="高中",
        )
        result = self.score_resume(resume, self.job)
        assert result.decision == "reject"

    def test_decision_shortlist_for_excellent(self):
        resume = self._make_resume(
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            years_experience=7,
            education="硕士",
            job_count=3,
        )
        result = self.score_resume(resume, self.job)
        assert result.decision == "shortlist"

    def test_result_to_dict_has_required_keys(self):
        resume = self._make_resume()
        result = self.score_resume(resume, self.job)
        d = result.to_dict()
        for key in ["candidate_id", "candidate_name", "total_score", "decision",
                    "skill_score", "matched_skills", "missing_skills"]:
            assert key in d

    def test_skill_in_raw_text_counts(self):
        """Skills found in raw_text should be counted even if not in skills list."""
        resume = self._make_resume(skills=[], raw_text="I have extensive Python experience with FastAPI and PostgreSQL.")
        result = self.score_resume(resume, self.job)
        assert result.skill_score > 0.0


# ── Batch Scoring Tests ────────────────────────────────────────────────────────
class TestBatchScoring:
    def setup_method(self):
        from tools.resume_scorer import JobRequirement, batch_score
        self.job = JobRequirement(
            title="Test",
            required_skills=["Python"],
            min_years_exp=1,
        )
        self.batch_score = batch_score

    def test_batch_returns_sorted_by_score(self):
        resumes = [
            {"id": "A", "name": "Low", "skills": [], "years_experience": 0, "education": "高中", "job_count": 1},
            {"id": "B", "name": "High", "skills": ["Python"], "years_experience": 5, "education": "硕士", "job_count": 2},
        ]
        results = self.batch_score(resumes, self.job)
        assert results[0].total_score >= results[1].total_score

    def test_batch_empty_resumes(self):
        results = self.batch_score([], self.job)
        assert results == []


# ── Candidate DB Tests ─────────────────────────────────────────────────────────
class TestCandidateDB:
    def setup_method(self):
        from tools import candidate_db
        # Reset state
        candidate_db._CANDIDATES.clear()
        from tools.candidate_db import add_candidate, get_candidate, update_candidate_status, list_candidates
        self.add_candidate = add_candidate
        self.get_candidate = get_candidate
        self.update_status = update_candidate_status
        self.list_candidates = list_candidates

    def test_add_candidate_success(self):
        result = self.add_candidate.invoke({
            "name": "Alice Zhang",
            "email": "alice@example.com",
            "position": "Python Engineer",
            "skills": "Python,FastAPI",
            "years_experience": 5,
            "education": "本科",
        })
        assert "✅" in result
        assert "C" in result  # ID begins with C

    def test_add_candidate_invalid_email(self):
        result = self.add_candidate.invoke({
            "name": "Bob",
            "email": "invalid",
            "position": "Engineer",
            "skills": "Python",
        })
        assert "❌" in result

    def test_add_candidate_empty_name_fails(self):
        result = self.add_candidate.invoke({
            "name": "  ",
            "email": "x@y.com",
            "position": "Engineer",
            "skills": "Python",
        })
        assert "❌" in result

    def test_get_nonexistent_candidate(self):
        result = self.get_candidate.invoke({"candidate_id": "XXXXXX"})
        assert "未找到" in result

    def test_update_status_valid(self):
        add_result = self.add_candidate.invoke({
            "name": "Eve", "email": "eve@e.com", "position": "QA", "skills": "Testing",
        })
        import re
        match = re.search(r"ID: (C[A-F0-9]+)", add_result)
        assert match is not None
        cid = match.group(1)
        result = self.update_status.invoke({"candidate_id": cid, "status": "shortlisted"})
        assert "shortlisted" in result

    def test_update_status_invalid_status(self):
        result = self.update_status.invoke({"candidate_id": "C12345", "status": "flying"})
        assert "无效状态" in result

    def test_list_candidates_empty(self):
        result = self.list_candidates.invoke({})
        data = json.loads(result)
        assert data["found"] is False


# ── Report Tool Tests ──────────────────────────────────────────────────────────
class TestReportTool:
    def setup_method(self):
        from tools.report_tool import generate_screening_report
        self.generate = generate_screening_report

    def test_generate_report_with_results(self, tmp_path, monkeypatch):
        import config
        monkeypatch.setattr(config, "REPORTS_DIR", str(tmp_path))
        import importlib
        import tools.report_tool as rt
        importlib.reload(rt)
        from tools.report_tool import generate_screening_report as gen
        results = [
            {"candidate_id": "R001", "candidate_name": "Alice", "total_score": 0.85,
             "decision": "shortlist", "skill_score": 0.9, "experience_score": 0.8,
             "education_score": 1.0, "stability_score": 1.0, "matched_skills": ["Python"], "missing_skills": [], "notes": []},
            {"candidate_id": "R002", "candidate_name": "Bob", "total_score": 0.4,
             "decision": "review", "skill_score": 0.5, "experience_score": 0.3,
             "education_score": 0.5, "stability_score": 0.7, "matched_skills": [], "missing_skills": ["Python"], "notes": []},
        ]
        report = gen.invoke({"position": "Python Engineer", "results_json": json.dumps(results)})
        assert "Python Engineer" in report
        assert "Alice" in report
        assert "入围" in report

    def test_generate_report_invalid_json(self):
        result = self.generate.invoke({"position": "Test", "results_json": "not json"})
        assert "❌" in result
