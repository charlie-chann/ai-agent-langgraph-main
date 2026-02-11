"""测试 project_24_openclaw_twitter"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tools.content_generator import generate_tweet, generate_thread, Tweet, TwitterThread
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags
from agent import run_generate_tweet, run_generate_thread, run_optimize_tags, run_plan_schedule, run_get_best_time, _sanitize
from config import MAX_TWEET_LENGTH, MAX_THREAD_TWEETS, MAX_HASHTAGS, PLATFORM


# ──────────────── content_generator — single tweet ────────────────

class TestTweetGenerator:
    def test_returns_tweet_dataclass(self):
        t = generate_tweet("AI")
        assert isinstance(t, Tweet)

    def test_char_count_within_limit(self):
        t = generate_tweet("Python programming")
        assert t.char_count <= MAX_TWEET_LENGTH

    def test_text_length_within_limit(self):
        t = generate_tweet("Machine Learning")
        assert len(t.text) <= MAX_TWEET_LENGTH

    def test_to_dict_has_keys(self):
        d = generate_tweet("Startup").to_dict()
        for key in ["平台", "内容", "字符数", "标签", "合规检查"]:
            assert key in d

    def test_compliance_pass_normal(self):
        t = generate_tweet("Productivity tips")
        assert t.compliance_check["passed"] is True

    def test_compliance_fail_prohibited(self):
        t = generate_tweet("gambling tips")
        assert t.compliance_check["passed"] is False

    def test_informative_style(self):
        t = generate_tweet("Tech", style="informative")
        assert len(t.text) > 0

    def test_engaging_style(self):
        t = generate_tweet("AI", style="engaging")
        assert len(t.text) > 0

    def test_promotional_style(self):
        t = generate_tweet("SaaS", style="promotional")
        assert len(t.text) > 0

    def test_thread_hook_style(self):
        t = generate_tweet("Python", style="thread_hook")
        assert len(t.text) > 0

    def test_hashtags_not_exceed_max(self):
        t = generate_tweet("Finance")
        assert len(t.hashtags) <= MAX_HASHTAGS

    def test_char_count_matches_text_length(self):
        t = generate_tweet("Career advice")
        assert t.char_count == len(t.text)


# ──────────────── content_generator — thread ────────────────

class TestThreadGenerator:
    def test_returns_thread_dataclass(self):
        th = generate_thread("AI trends", num_tweets=3)
        assert isinstance(th, TwitterThread)

    def test_thread_count_matches_requested(self):
        th = generate_thread("Python tips", num_tweets=5)
        assert th.total_tweets == 5

    def test_each_tweet_within_limit(self):
        th = generate_thread("Tech career", num_tweets=4)
        for tweet in th.tweets:
            assert len(tweet) <= MAX_TWEET_LENGTH

    def test_thread_not_exceed_max(self):
        th = generate_thread("Startup advice", num_tweets=MAX_THREAD_TWEETS + 5)
        assert th.total_tweets <= MAX_THREAD_TWEETS

    def test_to_dict_has_keys(self):
        d = generate_thread("Productivity").to_dict()
        for key in ["平台", "话题", "总条数", "推文列表", "标签", "合规检查"]:
            assert key in d

    def test_thread_has_hook_first(self):
        th = generate_thread("Machine Learning", num_tweets=3)
        assert len(th.tweets[0]) > 0

    def test_compliance_pass(self):
        th = generate_thread("OpenSource", num_tweets=3)
        assert th.compliance_check["passed"] is True

    def test_custom_points(self):
        points = ["Point A about Python", "Point B about testing"]
        th = generate_thread("Python", points=points, num_tweets=4)
        assert th.total_tweets == 4


# ──────────────── schedule_tool ────────────────

class TestScheduleTool:
    def test_plan_schedule_returns_dict(self):
        result = plan_schedule(PLATFORM, ["tweet1", "tweet2"], [13, 17], 5).to_dict()
        assert "发布时间表" in result

    def test_schedule_count_matches(self):
        posts = ["t1", "t2", "t3"]
        result = plan_schedule(PLATFORM, posts, [13], 10)
        assert result.posts_count == 3

    def test_daily_limit_respected(self):
        posts = ["p"] * 10
        result = plan_schedule(PLATFORM, posts, [13, 15, 17, 20], 4)
        dates = [s["日期"] for s in result.schedule]
        assert dates[0] != dates[9]

    def test_calculate_best_time(self):
        result = calculate_best_time(PLATFORM)
        assert isinstance(result, dict)
        assert "note" in result


# ──────────────── tag_optimizer ────────────────

class TestTagOptimizer:
    def test_returns_tag_result_dict(self):
        result = optimize_tags(PLATFORM, "AI").to_dict()
        assert "推荐标签" in result

    def test_max_tags_twitter_limit(self):
        result = optimize_tags(PLATFORM, "Tech", max_tags=3)
        assert len(result.recommended_tags) <= 3

    def test_engagement_score_range(self):
        result = optimize_tags(PLATFORM, "Python")
        assert 0 <= result.engagement_score <= 100

    def test_trending_tags_list(self):
        result = optimize_tags(PLATFORM, "Startup")
        assert isinstance(result.trending_tags, list)


# ──────────────── agent ────────────────

class TestAgent:
    def test_run_generate_tweet_dict(self):
        result = run_generate_tweet("AI tools")
        assert isinstance(result, dict)
        assert "内容" in result

    def test_run_generate_thread_dict(self):
        result = run_generate_thread("Python tips", num_tweets=3)
        assert isinstance(result, dict)
        assert "推文列表" in result

    def test_run_optimize_tags(self):
        result = run_optimize_tags("Machine Learning")
        assert "推荐标签" in result

    def test_run_plan_schedule(self):
        result = run_plan_schedule(["tweet1", "tweet2"])
        assert "发布时间表" in result

    def test_run_get_best_time(self):
        result = run_get_best_time()
        assert isinstance(result, dict)

    def test_sanitize_xss(self):
        assert "<script>" not in _sanitize("<script>alert(1)</script>")

    def test_sanitize_control_chars(self):
        assert "\x00" not in _sanitize("hello\x00world")
