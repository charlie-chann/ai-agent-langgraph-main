# tests/test_agent.py — project_16_education_agent
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest


class TestStudyPlanner:
    def setup_method(self):
        from tools.study_planner import generate_study_plan, generate_quiz, score_quiz
        self.plan = generate_study_plan
        self.quiz = generate_quiz
        self.score = score_quiz

    def test_plan_generated(self):
        p = self.plan("张三", "Python编程", daily_minutes=60)
        assert p.subject == "Python编程"
        assert p.daily_minutes == 60

    def test_plan_has_schedule(self):
        p = self.plan("李四", "高中数学", daily_minutes=90, target_days=14)
        assert len(p.topics_schedule) > 0

    def test_plan_has_milestones(self):
        p = self.plan("王五", "英语", daily_minutes=60)
        assert len(p.milestones) == 4

    def test_plan_weak_topics_prioritized(self):
        p = self.plan("测试", "Python编程", weak_topics=["基础语法"])
        # 第一个主题应包含弱点
        first_topics = p.topics_schedule[0]["学习主题"]
        assert any("基础语法" in t for t in first_topics)

    def test_plan_daily_minutes_clamped(self):
        p = self.plan("测试", "英语", daily_minutes=5)   # 低于最小值
        assert p.daily_minutes >= 30

    def test_plan_to_dict_keys(self):
        p = self.plan("测试", "数据结构")
        d = p.to_dict()
        for k in ["学生姓名", "科目", "开始日期", "结束日期", "每日学习分钟", "主题进度表", "里程碑"]:
            assert k in d

    def test_quiz_generated(self):
        questions = self.quiz("Python编程", difficulty="easy", count=1)
        assert len(questions) >= 1

    def test_quiz_has_required_keys(self):
        questions = self.quiz("Python编程", count=1)
        if questions:
            for k in ["题号", "题目", "选项", "正确答案"]:
                assert k in questions[0]

    def test_score_correct_answer(self):
        questions = self.quiz("Python编程", count=1)
        if questions:
            q = questions[0]
            answers = {q["题号"]: q["正确答案"]}
            result = self.score(questions, answers)
            assert result["正确数"] == 1
            assert result["是否及格"] or result["得分率"] >= 0

    def test_score_wrong_answer(self):
        questions = self.quiz("Python编程", count=1)
        if questions:
            answers = {questions[0]["题号"]: "Z"}  # 错误答案
            result = self.score(questions, answers)
            assert result["正确数"] == 0

    def test_quiz_empty_subject_returns_empty(self):
        questions = self.quiz("不存在的科目XYZ", count=3)
        # 应不崩溃，可能返回空列表
        assert isinstance(questions, list)

    def test_xss_in_name_sanitized(self):
        p = self.plan("<script>alert(1)</script>", "英语")
        assert "<script>" not in p.student_name


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize
        self.sanitize = _sanitize

    def test_truncates(self):
        assert len(self.sanitize("A" * 5000)) <= 2000
