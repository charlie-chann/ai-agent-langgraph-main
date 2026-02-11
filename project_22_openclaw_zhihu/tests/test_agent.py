"""测试 project_22_openclaw_zhihu"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tools.content_generator import generate_zhihu_answer, ZhihuContent
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags
from agent import run_generate_answer, run_optimize_tags, run_plan_schedule, run_get_best_time, _sanitize
from config import MAX_ANSWER_LENGTH, MAX_TAGS, PLATFORM


# ──────────────── content_generator ────────────────

class TestContentGenerator:
    def test_returns_dataclass(self):
        c = generate_zhihu_answer("如何提升工作效率？", "职场")
        assert isinstance(c, ZhihuContent)

    def test_content_type_is_answer(self):
        c = generate_zhihu_answer("什么是人工智能？", "科技")
        assert c.content_type == "answer"

    def test_body_not_exceed_max(self):
        c = generate_zhihu_answer("一个很长的问题" * 5, "教育")
        assert len(c.body) <= MAX_ANSWER_LENGTH

    def test_to_dict_keys(self):
        d = generate_zhihu_answer("如何理财？", "投资").to_dict()
        for key in ["平台", "类型", "标题/问题", "正文", "字数", "预估点赞", "合规检查"]:
            assert key in d

    def test_compliance_pass_normal(self):
        c = generate_zhihu_answer("如何保持健康？", "医疗")
        assert c.compliance_check["passed"] is True

    def test_compliance_fail_prohibited(self):
        c = generate_zhihu_answer("赌博技巧分析", "投资")
        assert c.compliance_check["passed"] is False

    def test_expert_level_higher_upvotes(self):
        expert = generate_zhihu_answer("职业规划", "职场", expertise_level="expert")
        beginner = generate_zhihu_answer("职业规划", "职场", expertise_level="beginner")
        assert expert.estimated_upvotes > beginner.estimated_upvotes

    def test_intermediate_level(self):
        c = generate_zhihu_answer("学习方法", "教育", expertise_level="intermediate")
        assert c.word_count > 0

    def test_tags_not_exceed_max(self):
        c = generate_zhihu_answer("Python学习", "科技")
        assert len(c.tags) <= MAX_TAGS

    def test_word_count_positive(self):
        c = generate_zhihu_answer("心理健康重要吗？", "心理")
        assert c.word_count > 0


# ──────────────── schedule_tool ────────────────

class TestScheduleTool:
    def test_plan_schedule_returns_dict(self):
        result = plan_schedule(PLATFORM, ["回答1", "回答2"], [12, 20], 2).to_dict()
        assert "发布时间表" in result

    def test_schedule_items_have_required_fields(self):
        result = plan_schedule(PLATFORM, ["内容"], [12], 3)
        entry = result.schedule[0]
        assert "日期" in entry and "时间" in entry

    def test_daily_limit_enforced(self):
        posts = ["p"] * 4
        result = plan_schedule(PLATFORM, posts, [12, 20], 2)
        dates = [s["日期"] for s in result.schedule]
        assert dates[0] != dates[3]

    def test_calculate_best_time(self):
        result = calculate_best_time(PLATFORM)
        assert isinstance(result, dict)


# ──────────────── tag_optimizer ────────────────

class TestTagOptimizer:
    def test_returns_tag_result_dict(self):
        result = optimize_tags(PLATFORM, "职场").to_dict()
        assert "推荐标签" in result

    def test_max_tags_respected(self):
        result = optimize_tags(PLATFORM, "科技", max_tags=3)
        assert len(result.recommended_tags) <= 3

    def test_engagement_score_range(self):
        result = optimize_tags(PLATFORM, "投资")
        assert 0 <= result.engagement_score <= 100


# ──────────────── agent ────────────────

class TestAgent:
    def test_run_generate_answer_dict(self):
        result = run_generate_answer("如何学好编程？", "科技")
        assert isinstance(result, dict)
        assert "正文" in result

    def test_run_optimize_tags(self):
        result = run_optimize_tags("职业发展")
        assert "推荐标签" in result

    def test_run_plan_schedule(self):
        result = run_plan_schedule(["回答1", "回答2"])
        assert "发布时间表" in result

    def test_run_get_best_time(self):
        result = run_get_best_time()
        assert isinstance(result, dict)

    def test_sanitize_xss(self):
        assert "<script>" not in _sanitize("<script>alert(1)</script>")

    def test_sanitize_control_chars(self):
        assert "\x00" not in _sanitize("hello\x00world")
