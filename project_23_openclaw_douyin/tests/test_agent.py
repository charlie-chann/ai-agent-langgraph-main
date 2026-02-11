"""测试 project_23_openclaw_douyin"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from tools.content_generator import generate_douyin_script, DouyinScript
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags
from agent import run_generate_script, run_optimize_tags, run_plan_schedule, run_get_best_time, _sanitize
from config import MAX_SCRIPT_LENGTH, MAX_TITLE_LENGTH, MAX_TAGS, PLATFORM, VIDEO_DURATIONS


# ──────────────── content_generator ────────────────

class TestContentGenerator:
    def test_returns_dataclass(self):
        s = generate_douyin_script("护肤")
        assert isinstance(s, DouyinScript)

    def test_title_not_exceed_max(self):
        s = generate_douyin_script("一个非常非常长的话题名称超出限制测试用例" * 2)
        assert len(s.title) <= MAX_TITLE_LENGTH

    def test_main_content_not_exceed_max(self):
        s = generate_douyin_script("健身")
        assert len(s.main_content) <= MAX_SCRIPT_LENGTH

    def test_to_dict_has_keys(self):
        d = generate_douyin_script("理财").to_dict()
        for key in ["平台", "视频标题", "开场钩子", "主体内容", "结尾引导", "话题标签", "脚本字数", "合规检查"]:
            assert key in d

    def test_compliance_pass_normal(self):
        s = generate_douyin_script("职场技能")
        assert s.compliance_check["passed"] is True

    def test_compliance_fail_prohibited(self):
        s = generate_douyin_script("赌博技巧", ["赌博"])
        assert s.compliance_check["passed"] is False

    def test_duration_snapped_to_valid(self):
        s = generate_douyin_script("知识分享", duration=45)
        assert s.duration_seconds in VIDEO_DURATIONS

    def test_short_video_15s(self):
        s = generate_douyin_script("搞笑", duration=15)
        assert s.duration_seconds == 15

    def test_long_video_180s(self):
        s = generate_douyin_script("深度分析", duration=180)
        assert s.duration_seconds == 180

    def test_hook_not_empty(self):
        s = generate_douyin_script("学习方法")
        assert len(s.hook) > 0

    def test_cta_not_empty(self):
        s = generate_douyin_script("美食")
        assert len(s.call_to_action) > 0

    def test_tags_not_exceed_max(self):
        s = generate_douyin_script("健身")
        assert len(s.hashtags) <= MAX_TAGS

    def test_word_count_positive(self):
        s = generate_douyin_script("vlog")
        assert s.word_count > 0

    def test_educational_style(self):
        s = generate_douyin_script("编程", style="educational")
        assert "点赞" in s.call_to_action or "收藏" in s.call_to_action

    def test_entertaining_style(self):
        s = generate_douyin_script("搞笑", style="entertaining")
        assert s.call_to_action != ""

    def test_motivational_style(self):
        s = generate_douyin_script("励志", style="motivational")
        assert s.call_to_action != ""


# ──────────────── schedule_tool ────────────────

class TestScheduleTool:
    def test_plan_schedule_returns_dict(self):
        result = plan_schedule(PLATFORM, ["视频1", "视频2"], [21, 22], 2).to_dict()
        assert "发布时间表" in result

    def test_schedule_count_matches(self):
        posts = ["v1", "v2", "v3"]
        result = plan_schedule(PLATFORM, posts, [18], 3)
        assert result.posts_count == 3

    def test_daily_limit_respected(self):
        posts = ["p"] * 6
        result = plan_schedule(PLATFORM, posts, [18, 21], 3)
        dates = [s["日期"] for s in result.schedule]
        assert dates[0] != dates[5]

    def test_calculate_best_time(self):
        result = calculate_best_time(PLATFORM)
        assert isinstance(result, dict)
        assert "说明" in result


# ──────────────── tag_optimizer ────────────────

class TestTagOptimizer:
    def test_returns_tag_result_dict(self):
        result = optimize_tags(PLATFORM, "知识").to_dict()
        assert "推荐标签" in result

    def test_max_tags_respected(self):
        result = optimize_tags(PLATFORM, "美食", max_tags=5)
        assert len(result.recommended_tags) <= 5

    def test_engagement_score_range(self):
        result = optimize_tags(PLATFORM, "搞笑")
        assert 0 <= result.engagement_score <= 100

    def test_trending_tags_list(self):
        result = optimize_tags(PLATFORM, "健身")
        assert isinstance(result.trending_tags, list)


# ──────────────── agent ────────────────

class TestAgent:
    def test_run_generate_script_dict(self):
        result = run_generate_script("健康饮食")
        assert isinstance(result, dict)
        assert "开场钩子" in result

    def test_run_optimize_tags(self):
        result = run_optimize_tags("知识分享")
        assert "推荐标签" in result

    def test_run_plan_schedule(self):
        result = run_plan_schedule(["视频1", "视频2"])
        assert "发布时间表" in result

    def test_run_get_best_time(self):
        result = run_get_best_time()
        assert isinstance(result, dict)

    def test_sanitize_xss(self):
        assert "<script>" not in _sanitize("<script>alert(1)</script>")

    def test_sanitize_control_chars(self):
        assert "\x00" not in _sanitize("hello\x00world")
