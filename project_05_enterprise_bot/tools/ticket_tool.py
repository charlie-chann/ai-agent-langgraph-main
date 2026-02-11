"""
tools/ticket_tool.py — 内部工单系统 LangChain 工具

【职责】
提供 create_ticket、list_tickets、close_ticket 三个 @tool 函数，
供 Agent 创建、查询、关闭 IT/HR 等类别的支持工单。

【设计原因】
演示企业 ITSM 集成模式：工具接口稳定，底层存储可无缝替换为 Jira/ServiceNow REST API；
入参校验与长度截断在工具层完成，降低 LLM 输出脏数据对存储的影响。
"""
import time
import uuid
from typing import Optional
from langchain_core.tools import tool
from loguru import logger

# 内存工单存储 — 生产环境替换为数据库或 Jira REST API
_TICKETS: dict[str, dict] = {}

# 合法优先级与类别枚举，用于 sanitize 非法 LLM 输入
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_CATEGORIES = {"it", "hr", "finance", "facilities", "security", "general"}


@tool
def create_ticket(
    title: str,
    description: str,
    priority: str = "medium",
    category: str = "general",
    assignee: str = "",
    reporter: str = "anonymous",
) -> str:
    """Create a support/work ticket in the internal ticketing system.
    Args:
        title: Short title of the issue (max 100 chars)
        description: Detailed description
        priority: low | medium | high | critical
        category: it | hr | finance | facilities | security | general
        assignee: username of the person to assign to (optional)
        reporter: username of the person reporting
    Returns: ticket ID and confirmation
    """
    # 清洗并截断用户/LLM 传入的字段，防止超长或非法枚举值
    title = title.strip()[:100]
    description = description.strip()[:2000]
    priority = priority.lower() if priority.lower() in VALID_PRIORITIES else "medium"
    category = category.lower() if category.lower() in VALID_CATEGORIES else "general"

    # 生成短 UUID 前缀作为人类可读的工单号
    ticket_id = f"TKT-{str(uuid.uuid4())[:6].upper()}"
    _TICKETS[ticket_id] = {
        "id": ticket_id,
        "title": title,
        "description": description,
        "priority": priority,
        "category": category,
        "assignee": assignee,
        "reporter": reporter,
        "status": "open",
        "created_at": int(time.time()),
    }
    logger.info(f"[create_ticket] {ticket_id}: {title!r}")
    return f"Ticket created: {ticket_id}\nTitle: {title}\nPriority: {priority}\nCategory: {category}"


@tool
def list_tickets(status: str = "open", reporter: str = "", limit: int = 10) -> str:
    """List tickets from the ticketing system.
    Args:
        status: open | closed | all
        reporter: filter by reporter username (empty = all)
        limit: max number of tickets to return (1-20)
    Returns: formatted list of tickets
    """
    # 限制返回条数在 1~20，避免 LLM 请求过大结果集
    limit = max(1, min(limit, 20))
    tickets = list(_TICKETS.values())
    # 按状态筛选：all 表示不过滤
    if status != "all":
        tickets = [t for t in tickets if t["status"] == status]
    # 可选：仅列出指定报告人的工单（员工查看「我的工单」场景）
    if reporter:
        tickets = [t for t in tickets if t["reporter"] == reporter]
    # 按创建时间倒序，取前 limit 条
    tickets = sorted(tickets, key=lambda x: x["created_at"], reverse=True)[:limit]

    if not tickets:
        return "No tickets found."

    lines = [f"Found {len(tickets)} ticket(s):"]
    for t in tickets:
        lines.append(
            f"  [{t['id']}] {t['title']} | {t['priority'].upper()} | {t['status']} | by {t['reporter']}"
        )
    return "\n".join(lines)


@tool
def close_ticket(ticket_id: str, resolution: str = "") -> str:
    """Close an existing ticket.
    Args:
        ticket_id: The ticket ID (e.g. TKT-ABC123)
        resolution: How the issue was resolved
    Returns: confirmation message
    """
    ticket_id = ticket_id.strip().upper()
    if ticket_id not in _TICKETS:
        return f"Ticket {ticket_id} not found."
    # 更新状态与解决说明，不物理删除记录以便审计
    _TICKETS[ticket_id]["status"] = "closed"
    _TICKETS[ticket_id]["resolution"] = resolution.strip()[:500]
    logger.info(f"[close_ticket] {ticket_id}")
    return f"Ticket {ticket_id} closed. Resolution: {resolution or 'N/A'}"
