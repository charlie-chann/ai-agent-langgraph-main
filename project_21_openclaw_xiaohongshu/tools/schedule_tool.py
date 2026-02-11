# tools/schedule_tool.py — 发布时间优化工具
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SchedulePlan:
    platform: str
    posts_count: int
    schedule: list[dict]
    next_post_time: str

    def to_dict(self) -> dict:
        return {
            "平台": self.platform,
            "计划发布数": self.posts_count,
            "发布时间表": self.schedule,
            "下一次发布": self.next_post_time,
        }


def plan_schedule(
    platform: str,
    posts: list[str],
    optimal_hours: list[int],
    daily_limit: int,
    start_date: date | None = None,
) -> SchedulePlan:
    """为帖子列表生成发布时间计划。"""
    if start_date is None:
        start_date = date.today()

    schedule = []
    current_date = start_date
    daily_count = 0
    hour_idx = 0

    for i, post in enumerate(posts):
        if daily_count >= daily_limit:
            current_date += timedelta(days=1)
            daily_count = 0
            hour_idx = 0

        hour = optimal_hours[hour_idx % len(optimal_hours)]
        schedule.append({
            "序号": i + 1,
            "日期": str(current_date),
            "时间": f"{hour:02d}:00",
            "内容预览": post[:30] + ("…" if len(post) > 30 else ""),
        })
        daily_count += 1
        hour_idx += 1

    next_time = f"{schedule[0]['日期']} {schedule[0]['时间']}" if schedule else str(date.today())
    return SchedulePlan(platform=platform, posts_count=len(posts), schedule=schedule, next_post_time=next_time)


def calculate_best_time(platform: str) -> dict:
    """返回平台最佳发布时间建议。"""
    TIME_ADVICE = {
        "xiaohongshu": {"早晨": "07:00-09:00", "午间": "12:00-13:00", "晚间": "20:00-23:00", "说明": "女性用户为主，午间和晚上活跃"},
        "weibo": {"早晨": "07:00-09:00", "午间": "12:00-14:00", "晚间": "18:00-22:00", "说明": "热点话题在白天爆发"},
        "zhihu": {"工作日": "12:00-14:00", "晚间": "20:00-23:00", "说明": "知识型用户，思考时间更长"},
        "douyin": {"早晨": "07:00-09:00", "午间": "11:00-13:00", "晚间": "19:00-23:00", "说明": "算法推流，全天可发"},
    }
    return TIME_ADVICE.get(platform, {"说明": "建议在用户活跃高峰期发布"})
