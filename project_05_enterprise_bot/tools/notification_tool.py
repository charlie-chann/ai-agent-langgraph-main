"""
tools/notification_tool.py — 企业通知发送 LangChain 工具

【职责】
提供 send_notification（向 Slack/Email/Teams 发送消息）与 get_notifications
（审计最近发送记录）两个 @tool 函数。

【设计原因】
高权限操作（经理/管理员发 urgent 通知）需经 Agent + RBAC 双重 gate；
当前用内存列表模拟发送结果，接口形状与真实 Webhook/SMTP 集成保持一致。
"""
from langchain_core.tools import tool
from loguru import logger

# 演示用通知发送记录 — 生产环境对接 Slack API / SMTP / Teams Webhook
_NOTIFICATIONS: list[dict] = []


@tool
def send_notification(
    to: str,
    message: str,
    channel: str = "slack",
    priority: str = "normal",
) -> str:
    """Send a notification to a user or channel via Slack, Email, or Teams.
    Args:
        to: recipient username or email (e.g. '@alice' or 'alice@company.com')
        message: notification message content (max 500 chars)
        channel: slack | email | teams
        priority: normal | urgent
    Returns: confirmation of notification sent
    """
    # 清洗收件人与消息长度，校验 channel/priority 枚举
    to = to.strip()[:100]
    message = message.strip()[:500]
    channel = channel.lower() if channel.lower() in {"slack", "email", "teams"} else "slack"
    priority = priority.lower() if priority.lower() in {"normal", "urgent"} else "normal"

    if not to or not message:
        return "Error: 'to' and 'message' are required."

    # 追加到内存队列，模拟「已发送」状态供审计查询
    _NOTIFICATIONS.append({
        "to": to,
        "message": message,
        "channel": channel,
        "priority": priority,
    })
    logger.info(f"[notify] → {to} via {channel}: {message[:50]!r}")
    return f"Notification sent to {to} via {channel} ({'🚨 URGENT' if priority == 'urgent' else '📢 Normal'})."


@tool
def get_notifications(limit: int = 5) -> str:
    """Retrieve recent notifications that were sent (for audit/review).
    Input: number of recent notifications to retrieve (1-20).
    """
    limit = max(1, min(limit, 20))
    # 取列表尾部最近 limit 条，再倒序展示（最新的在前）
    recent = _NOTIFICATIONS[-limit:]
    if not recent:
        return "No notifications sent yet."
    lines = [f"Recent {len(recent)} notification(s):"]
    for n in reversed(recent):
        lines.append(f"  → {n['to']} via {n['channel']}: {n['message'][:80]}...")
    return "\n".join(lines)
