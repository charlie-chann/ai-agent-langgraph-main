# tools/schedule_tool.py — 发布时间优化工具（共用于所有 openclaw 项目）
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass
class SchedulePlan:
    """发布计划数据类。"""
    platform: str
    posts_count: int
    schedule: list[dict]   # [{date, time, content_preview}]
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
    """
    为帖子列表生成发布时间计划。

    Args:
        platform: 平台名称
        posts: 帖子内容列表（每条取前30字作为预览）
        optimal_hours: 最佳发布小时列表
        daily_limit: 每日发布上限
        start_date: 开始日期（默认今天）

    Returns:
        SchedulePlan
    """
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

    return SchedulePlan(
        platform=platform,
        posts_count=len(posts),
        schedule=schedule,
        next_post_time=next_time,
    )


def calculate_best_time(platform: str, audience_timezone: str = "Asia/Shanghai") -> dict:
    """
    返回各平台最佳发布时间窗口建议。
    """
    best_times = {
        "weibo":       {"工作日": "08:00, 12:00, 18:00, 21:00", "周末": "10:00, 15:00, 20:00"},
        "xiaohongshu": {"工作日": "10:00, 20:00, 22:00",        "周末": "11:00, 15:00, 21:00"},
        "zhihu":       {"工作日": "09:00, 14:00, 20:00",        "周末": "10:00, 20:00"},
        "douyin":      {"工作日": "12:00, 18:00, 21:00, 22:00", "周末": "12:00, 18:00, 21:00"},
        "twitter":     {"工作日": "13:00, 15:00, 17:00 UTC",    "周末": "14:00, 18:00 UTC"},
    }
    return {
        "平台": platform,
        "时区": audience_timezone,
        "建议发布时间": best_times.get(platform, {"通用": "09:00, 12:00, 18:00, 21:00"}),
    }
