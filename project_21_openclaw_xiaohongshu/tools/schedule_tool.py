# tools/schedule_tool.py — 内容发布排期工具
#
# 【主入口】
#   plan_schedule()       → 为多篇笔记分配发布日期和时间
#   calculate_best_time() → 返回平台最佳发布时段建议
# 【被谁调用】agent.run_plan_schedule() / agent.run_get_best_time()
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class SchedulePlan:
    """发布计划结果，to_dict() 供 UI/API 展示。"""
    platform: str
    posts_count: int
    schedule: list[dict]      # 每篇的日期、时间、内容预览
    next_post_time: str       # 最近一次建议发布时间

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
    【主入口】为帖子列表生成发布时间计划。

    规则：每天最多发 daily_limit 篇，按 optimal_hours 轮流分配时段，
    超出当日上限则顺延到第二天。
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
    return SchedulePlan(platform=platform, posts_count=len(posts), schedule=schedule, next_post_time=next_time)


def calculate_best_time(platform: str) -> dict:
    """【主入口】返回各平台最佳发布时段建议（静态数据）。"""
    TIME_ADVICE = {
        "xiaohongshu": {"早晨": "07:00-09:00", "午间": "12:00-13:00", "晚间": "20:00-23:00", "说明": "女性用户为主，午间和晚上活跃"},
        "weibo": {"早晨": "07:00-09:00", "午间": "12:00-14:00", "晚间": "18:00-22:00", "说明": "热点话题在白天爆发"},
        "zhihu": {"工作日": "12:00-14:00", "晚间": "20:00-23:00", "说明": "知识型用户，思考时间更长"},
        "douyin": {"早晨": "07:00-09:00", "午间": "11:00-13:00", "晚间": "19:00-23:00", "说明": "算法推流，全天可发"},
    }
    return TIME_ADVICE.get(platform, {"说明": "建议在用户活跃高峰期发布"})
