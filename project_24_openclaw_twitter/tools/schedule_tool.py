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
    """为推文列表生成发布时间计划。"""
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
            "时间(UTC)": f"{hour:02d}:00",
            "内容预览": post[:50] + ("…" if len(post) > 50 else ""),
        })
        daily_count += 1
        hour_idx += 1

    next_time = f"{schedule[0]['日期']} {schedule[0]['时间(UTC)']} UTC" if schedule else str(date.today())
    return SchedulePlan(platform=platform, posts_count=len(posts), schedule=schedule, next_post_time=next_time)


def calculate_best_time(platform: str) -> dict:
    """返回 Twitter 最佳发布时间建议（UTC）。"""
    TIME_ADVICE = {
        "twitter": {
            "morning_US": "13:00-15:00 UTC (8-10am EST)",
            "afternoon_US": "17:00-19:00 UTC (12-2pm EST)",
            "evening_US": "20:00-22:00 UTC (3-5pm EST)",
            "note": "Twitter/X peaks during US business hours. Tech audiences most active Tue-Thu.",
        },
    }
    return TIME_ADVICE.get(platform, {"note": "Post during peak audience timezone"})
