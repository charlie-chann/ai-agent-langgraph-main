# tools/notification_tool.py — Mock notification sender (Slack/Email/Teams)
from langchain_core.tools import tool
from loguru import logger

# Mock notification store — replace with Slack API / SMTP / Teams webhook
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
    # Sanitize
    to = to.strip()[:100]
    message = message.strip()[:500]
    channel = channel.lower() if channel.lower() in {"slack", "email", "teams"} else "slack"
    priority = priority.lower() if priority.lower() in {"normal", "urgent"} else "normal"

    if not to or not message:
        return "Error: 'to' and 'message' are required."

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
    recent = _NOTIFICATIONS[-limit:]
    if not recent:
        return "No notifications sent yet."
    lines = [f"Recent {len(recent)} notification(s):"]
    for n in reversed(recent):
        lines.append(f"  → {n['to']} via {n['channel']}: {n['message'][:80]}...")
    return "\n".join(lines)
