# tests/test_agent.py — project_05_enterprise_bot
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ── RBAC tests ────────────────────────────────────────────────────────────────
def test_rbac_employee_permissions():
    from tools.rbac import get_user_role, get_allowed_tools, check_permission
    role = get_user_role("emp_charlie")
    assert role == "employee"
    allowed = get_allowed_tools("emp_charlie")
    assert "search_kb" in allowed
    assert "create_ticket" in allowed


def test_rbac_admin_has_more_permissions():
    from tools.rbac import get_allowed_tools
    admin_tools = get_allowed_tools("admin_user")
    emp_tools = get_allowed_tools("emp_charlie")
    assert len(admin_tools) > len(emp_tools)


def test_rbac_permission_denied():
    from tools.rbac import check_permission
    allowed, reason = check_permission("emp_charlie", "close_ticket")
    # close_ticket is not in employee role
    assert allowed is False
    assert "denied" in reason.lower()


def test_rbac_unknown_user_defaults_to_employee():
    from tools.rbac import get_user_role
    role = get_user_role("totally_unknown_user_xyz")
    assert role == "employee"


# ── KB tool tests ─────────────────────────────────────────────────────────────
def test_kb_search_returns_result():
    from tools.kb_tool import search_kb
    result = search_kb.invoke("VPN setup")
    assert "VPN" in result or "vpn" in result.lower()


def test_kb_search_empty_returns_error():
    from tools.kb_tool import search_kb
    result = search_kb.invoke("")
    assert "Please provide" in result or "query" in result.lower()


def test_kb_search_no_match():
    from tools.kb_tool import search_kb
    result = search_kb.invoke("zzz_no_match_topic_xyz_abc")
    assert "No KB" in result or "not found" in result.lower()


# ── Ticket tool tests ─────────────────────────────────────────────────────────
def test_create_and_list_ticket():
    from tools.ticket_tool import create_ticket, list_tickets
    result = create_ticket.invoke({
        "title": "Test ticket",
        "description": "Test description",
        "priority": "high",
        "category": "IT",
    })
    assert "TKT-" in result
    # Extract ticket ID (format: TKT-XXXXXX where X is hex)
    import re
    match = re.search(r"TKT-[A-F0-9]+", result)
    assert match is not None


def test_close_nonexistent_ticket():
    from tools.ticket_tool import close_ticket
    result = close_ticket.invoke({"ticket_id": "TKT-9999", "resolution": "test"})
    assert "not found" in result.lower()


# ── Notification tests ────────────────────────────────────────────────────────
def test_send_notification():
    from tools.notification_tool import send_notification
    result = send_notification.invoke({
        "to": "@alice",
        "message": "Your ticket has been resolved",
        "channel": "slack",
        "priority": "normal",
    })
    assert "sent" in result.lower()


def test_send_notification_invalid_channel_defaults():
    from tools.notification_tool import send_notification
    result = send_notification.invoke({
        "to": "@bob",
        "message": "Hello",
        "channel": "carrier_pigeon",  # invalid
        "priority": "normal",
    })
    # Should default to slack and still succeed
    assert "sent" in result.lower()
