# tools/ticket_tool.py — in-memory ticket system (replace with Jira/ServiceNow API)
import time
import uuid
from typing import Optional
from langchain_core.tools import tool
from loguru import logger

# In-memory store — in production replace with DB / Jira REST API
_TICKETS: dict[str, dict] = {}

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
    # Sanitize inputs
    title = title.strip()[:100]
    description = description.strip()[:2000]
    priority = priority.lower() if priority.lower() in VALID_PRIORITIES else "medium"
    category = category.lower() if category.lower() in VALID_CATEGORIES else "general"

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
    limit = max(1, min(limit, 20))
    tickets = list(_TICKETS.values())
    if status != "all":
        tickets = [t for t in tickets if t["status"] == status]
    if reporter:
        tickets = [t for t in tickets if t["reporter"] == reporter]
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
    _TICKETS[ticket_id]["status"] = "closed"
    _TICKETS[ticket_id]["resolution"] = resolution.strip()[:500]
    logger.info(f"[close_ticket] {ticket_id}")
    return f"Ticket {ticket_id} closed. Resolution: {resolution or 'N/A'}"
