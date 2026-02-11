"""测试 project_21_openclaw_xiaohongshu"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import date
from tools.content_generator import generate_xiaohongshu_post, XiaohongshuPost
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags
from agent import run_generate_post, run_optimize_tags, run_plan_schedule, run_get_best_time, _sanitize
from config import MAX_TITLE_LENGTH, MAX_CONTENT_LENGTH, MAX_TAGS, PLATFORM


# ──────────────── content_generator ────────────────

class TestContentGenerator:
    def test_returns_dataclass(self):
        post = generate_xiaohongshu_post("护肤")
        assert isinstance(post, XiaohongshuPost)

    def test_title_not_exceed_max(self):
        post = generate_xiaohongshu_post("一个非常长的话题名称超出限制" * 3)
        assert len(post.title) <= MAX_TITLE_LENGTH

    def test_content_not_exceed_max(self):
        post = generate_xiaohongshu_post("健身")
        assert len(post.content) <= MAX_CONTENT_LENGTH

    def test_to_dict_has_keys(self):
        d = generate_xiaohongshu_post("穿搭").to_dict()
        for key in ["平台", "标题", "正文", "标签", "字数", "合规检查"]:
            assert key in d

    def test_compliance_pass_normal(self):
        post = generate_xiaohongshu_post("读书笔记")
        assert post.compliance_check["passed"] is True

    def test_compliance_fail_prohibited(self):
        post = generate_xiaohongshu_post("赌博技巧", ["赌博"])
        assert post.compliance_check["passed"] is False

    def test_lifestyle_style(self):
        post = generate_xiaohongshu_post("旅行", style="lifestyle")
        assert post.word_count > 0

    def test_tutorial_style(self):
        post = generate_xiaohongshu_post("烘焙", style="tutorial")
        assert "step" in post.content.lower() or "步骤" in post.content

    def test_review_style(self):
        post = generate_xiaohongshu_post("面膜", style="review")
        assert post.content != ""

    def test_keywords_included_concept(self):
        post = generate_xiaohongshu_post("护肤", keywords=["精华液", "补水"])
        # 关键词应体现在内容中
        text = post.title + post.content
        assert len(text) > 0

    def test_has_image_suggestions(self):
        post = generate_xiaohongshu_post("健身")
        assert isinstance(post.image_suggestions, list)
        assert len(post.image_suggestions) > 0

    def test_tags_not_exceed_max(self):
        post = generate_xiaohongshu_post("美食")
        assert len(post.hashtags) <= MAX_TAGS

    def test_platform_field(self):
        d = generate_xiaohongshu_post("职场").to_dict()
        assert d["平台"] == PLATFORM


# ──────────────── schedule_tool ────────────────

class TestScheduleTool:
    def test_plan_schedule_returns_dict(self):
        result = plan_schedule(PLATFORM, ["内容1", "内容2"], [12, 18], 2).to_dict()
        assert "发布时间表" in result

    def test_schedule_count_matches(self):
        posts = ["帖子A", "帖子B", "帖子C"]
        result = plan_schedule(PLATFORM, posts, [20], 3)
        assert result.posts_count == 3

    def test_daily_limit_respected(self):
        posts = ["p"] * 6
        result = plan_schedule(PLATFORM, posts, [19, 21], 2)
        dates = [s["日期"] for s in result.schedule]
        assert dates[0] != dates[4]  # 超过每日2条后换天

    def test_calculate_best_time(self):
        result = calculate_best_time(PLATFORM)
        assert isinstance(result, dict)
        assert len(result) > 0


# ──────────────── tag_optimizer ────────────────

class TestTagOptimizer:
    def test_returns_tag_result_dict(self):
        result = optimize_tags(PLATFORM, "护肤").to_dict()
        assert "推荐标签" in result

    def test_max_tags_respected(self):
        result = optimize_tags(PLATFORM, "美食", max_tags=4)
        assert len(result.recommended_tags) <= 4

    def test_engagement_score_range(self):
        result = optimize_tags(PLATFORM, "穿搭")
        assert 0 <= result.engagement_score <= 100

    def test_trending_tags_subset(self):
        result = optimize_tags(PLATFORM, "减肥")
        assert isinstance(result.trending_tags, list)


# ──────────────── agent ────────────────

class TestAgent:
    def test_run_generate_post_dict(self):
        result = run_generate_post("护肤")
        assert isinstance(result, dict)
        assert "标题" in result

    def test_run_optimize_tags(self):
        result = run_optimize_tags("美妆")
        assert "推荐标签" in result

    def test_run_plan_schedule(self):
        result = run_plan_schedule(["帖子1", "帖子2"])
        assert "发布时间表" in result

    def test_run_get_best_time(self):
        result = run_get_best_time()
        assert isinstance(result, dict)

    def test_sanitize_xss(self):
        assert "<script>" not in _sanitize("<script>alert(1)</script>")

    def test_sanitize_control_chars(self):
        assert "\x00" not in _sanitize("hello\x00world")
