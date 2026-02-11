# tests/test_agent.py — project_20_openclaw_weibo
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import pytest


class TestWeiboContentGenerator:
    def setup_method(self):
        from tools.content_generator import generate_weibo_post, generate_batch, _check_compliance
        self.generate = generate_weibo_post
        self.batch = generate_batch
        self.compliance = _check_compliance

    def test_generate_post_not_empty(self):
        post = self.generate("科技")
        assert len(post.content) > 0

    def test_generate_post_within_length(self):
        from config import MAX_CONTENT_LENGTH
        post = self.generate("生活", tone="conversational")
        assert post.word_count <= MAX_CONTENT_LENGTH

    def test_generate_post_has_hashtags(self):
        post = self.generate("美食")
        assert len(post.hashtags) > 0

    def test_generate_post_professional_tone(self):
        post = self.generate("职场", tone="professional")
        assert len(post.content) > 0

    def test_generate_post_humorous_tone(self):
        post = self.generate("健身", tone="humorous")
        assert len(post.content) > 0

    def test_generate_post_compliance_passed(self):
        post = self.generate("科技")
        assert post.compliance_check.get("passed") is True

    def test_prohibited_content_flagged(self):
        result = self.compliance("这是赌博诈骗内容")
        assert result["passed"] is False
        assert len(result["violations"]) > 0

    def test_clean_content_passes(self):
        result = self.compliance("今天天气很好，分享一下科技资讯")
        assert result["passed"] is True

    def test_batch_generates_multiple(self):
        posts = self.batch("旅行", count=3)
        assert len(posts) == 3

    def test_batch_limit_respected(self):
        posts = self.batch("科技", count=20)  # 超过每日限制
        assert len(posts) <= 10

    def test_xss_in_topic(self):
        post = self.generate("<script>alert(1)</script>科技")
        assert "<script>" not in post.content

    def test_to_dict_keys(self):
        post = self.generate("教育")
        d = post.to_dict()
        for k in ["平台", "内容", "话题标签", "字数", "合规检查"]:
            assert k in d


class TestScheduleTool:
    def setup_method(self):
        from tools.schedule_tool import plan_schedule, calculate_best_time
        self.plan = plan_schedule
        self.best_time = calculate_best_time

    def test_schedule_generates_timeline(self):
        posts = ["帖子内容1", "帖子内容2", "帖子内容3"]
        plan = self.plan("weibo", posts, [8, 12, 18, 21], 10)
        assert plan.posts_count == 3
        assert len(plan.schedule) == 3

    def test_daily_limit_enforced(self):
        posts = [f"帖子{i}" for i in range(15)]
        from datetime import date
        plan = self.plan("weibo", posts, [8, 12, 18, 21], 5, date.today())
        # 超过每日限制的应该推到下一天
        dates_used = set(s["日期"] for s in plan.schedule)
        assert len(dates_used) >= 3  # 15 posts / 5 per day = 3 days

    def test_best_time_weibo(self):
        result = self.best_time("weibo")
        assert "建议发布时间" in result
        assert "工作日" in result["建议发布时间"]


class TestTagOptimizer:
    def setup_method(self):
        from tools.tag_optimizer import optimize_tags
        self.optimize = optimize_tags

    def test_returns_recommended_tags(self):
        result = self.optimize("weibo", "科技", max_tags=5)
        assert len(result.recommended_tags) <= 5

    def test_engagement_score_range(self):
        result = self.optimize("weibo", "生活")
        assert 0 <= result.engagement_score <= 100

    def test_to_dict_keys(self):
        result = self.optimize("weibo", "美食")
        d = result.to_dict()
        for k in ["平台", "推荐标签", "热门标签", "预估互动得分"]:
            assert k in d


class TestAgentSanitization:
    def setup_method(self):
        from agent import _sanitize
        self.sanitize = _sanitize

    def test_removes_control_chars(self):
        assert "\x00" not in self.sanitize("text\x00injection")

    def test_truncates(self):
        assert len(self.sanitize("A" * 5000)) <= 2000
