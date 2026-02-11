# tools/ticket_tool.py — 客服工单管理工具（内存存储，生产可替换为数据库）
"""
工单全生命周期管理：创建、查询、更新、关闭、SLA追踪。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from langchain_core.tools import tool
from loguru import logger

from config import SLA_HOURS

# ── 内存工单存储（生产环境替换为数据库） ─────────────────────────────────────
_TICKETS: dict[str, dict] = {}
_TICKET_COUNTER = {"n": 1000}  # 工单编号起始值

# 工单状态定义
TICKET_STATUSES = {"open", "in_progress", "pending_user", "resolved", "closed", "escalated"}
# 优先级定义
TICKET_PRIORITIES = {"P1", "P2", "P3", "P4"}

# 意图到优先级的映射
_INTENT_PRIORITY_MAP = {
    "complaint": "P2",
    "refund": "P2",
    "account_issue": "P1",
    "billing": "P2",
    "technical_support": "P3",
    "order_status": "P3",
    "query_faq": "P4",
    "general": "P4",
}


def _new_ticket_id() -> str:
    """生成唯一工单编号。"""
    tid = f"TK{_TICKET_COUNTER['n']:05d}"
    _TICKET_COUNTER["n"] += 1
    return tid


def _sla_deadline(priority: str, created_at: str) -> str:
    """计算SLA截止时间。"""
    hours = SLA_HOURS.get(priority, 24)
    dt = datetime.fromisoformat(created_at)
    deadline = dt + timedelta(hours=hours)
    return deadline.isoformat()


@tool
def create_ticket(
    user_id: str,
    title: str,
    description: str,
    intent: str = "general",
    priority: str = "",
) -> str:
    """创建新的客服工单。
    参数：
        user_id: 用户ID或姓名
        title: 工单标题（简短描述问题，50字以内）
        description: 详细问题描述
        intent: 问题意图（complaint/refund/technical_support/order_status/billing/account_issue/general）
        priority: 优先级（P1=紧急/P2=高/P3=正常/P4=低，不填则根据意图自动判断）
    返回：工单详情JSON。
    """
    if not title.strip() or not user_id.strip():
        return "错误：用户ID和工单标题不能为空"

    ticket_id = _new_ticket_id()
    auto_priority = _INTENT_PRIORITY_MAP.get(intent, "P3")
    final_priority = priority if priority in TICKET_PRIORITIES else auto_priority
    now = datetime.now(timezone.utc).isoformat()

    ticket = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "title": title[:100],
        "description": description[:500],
        "intent": intent,
        "priority": final_priority,
        "status": "open",
        "created_at": now,
        "updated_at": now,
        "sla_deadline": _sla_deadline(final_priority, now),
        "comments": [],
        "assigned_to": None,
    }
    _TICKETS[ticket_id] = ticket
    logger.info(f"[ticket] 创建 {ticket_id} user={user_id!r} priority={final_priority}")

    sla_h = SLA_HOURS.get(final_priority, 24)
    return json.dumps({
        "success": True,
        "ticket_id": ticket_id,
        "message": f"工单 {ticket_id} 已创建，优先级 {final_priority}，预计 {sla_h} 小时内处理",
        "ticket": ticket,
    }, ensure_ascii=False, indent=2)


@tool
def get_ticket(ticket_id: str) -> str:
    """查询工单详情。
    输入：工单编号（如 TK01000）
    返回：工单完整信息。
    """
    ticket_id = ticket_id.strip().upper()
    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        return json.dumps({"found": False, "message": f"工单 {ticket_id} 不存在"}, ensure_ascii=False)
    return json.dumps({"found": True, "ticket": ticket}, ensure_ascii=False, indent=2)


@tool
def list_user_tickets(user_id: str) -> str:
    """查询指定用户的所有工单。
    输入：用户ID
    返回：该用户的工单列表（按创建时间倒序）。
    """
    user_id = user_id.strip()
    tickets = [t for t in _TICKETS.values() if t["user_id"] == user_id]
    tickets.sort(key=lambda x: x["created_at"], reverse=True)

    summary = [
        {
            "ticket_id": t["ticket_id"],
            "title": t["title"],
            "status": t["status"],
            "priority": t["priority"],
            "created_at": t["created_at"],
        }
        for t in tickets[:10]
    ]
    return json.dumps({
        "user_id": user_id,
        "total": len(tickets),
        "tickets": summary,
    }, ensure_ascii=False, indent=2)


@tool
def update_ticket_status(ticket_id: str, status: str, comment: str = "") -> str:
    """更新工单状态并添加备注。
    参数：
        ticket_id: 工单编号
        status: 新状态（open/in_progress/pending_user/resolved/closed/escalated）
        comment: 更新说明（可选）
    """
    ticket_id = ticket_id.strip().upper()
    if status not in TICKET_STATUSES:
        return f"无效状态：{status}，有效状态：{', '.join(TICKET_STATUSES)}"

    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        return f"工单 {ticket_id} 不存在"

    old_status = ticket["status"]
    ticket["status"] = status
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    if comment:
        ticket["comments"].append({
            "time": ticket["updated_at"],
            "content": comment,
        })
    logger.info(f"[ticket] 更新 {ticket_id} {old_status} → {status}")
    return json.dumps({
        "success": True,
        "ticket_id": ticket_id,
        "old_status": old_status,
        "new_status": status,
        "message": f"工单 {ticket_id} 状态已更新为：{status}",
    }, ensure_ascii=False)


@tool
def escalate_ticket(ticket_id: str, reason: str) -> str:
    """将工单升级到人工客服处理。
    参数：
        ticket_id: 工单编号
        reason: 升级原因
    返回：升级结果。
    """
    ticket_id = ticket_id.strip().upper()
    ticket = _TICKETS.get(ticket_id)
    if not ticket:
        return f"工单 {ticket_id} 不存在"

    ticket["status"] = "escalated"
    ticket["priority"] = "P1"
    ticket["assigned_to"] = "人工客服团队"
    ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
    ticket["comments"].append({
        "time": ticket["updated_at"],
        "content": f"[升级到人工] 原因：{reason}",
    })
    logger.warning(f"[ticket] 升级 {ticket_id} reason={reason!r}")
    return json.dumps({
        "success": True,
        "ticket_id": ticket_id,
        "message": f"工单 {ticket_id} 已升级到人工客服（P1优先级），预计30分钟内响应",
        "assigned_to": "人工客服团队",
    }, ensure_ascii=False)
