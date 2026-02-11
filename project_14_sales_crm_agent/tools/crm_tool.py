# tools/crm_tool.py — CRM 数据管理工具
from __future__ import annotations

import uuid
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


# 内存存储（生产环境替换为数据库）
_leads_db: dict[str, dict] = {}
_activities_db: list[dict] = []


@dataclass
class CRMRecord:
    """CRM 线索记录。"""
    lead_id: str
    name: str
    company: str
    email: str
    phone: str
    status: Literal["new", "contacted", "qualified", "proposal", "closed_won", "closed_lost"]
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: str(date.today()))
    updated_at: str = field(default_factory=lambda: str(date.today()))

    def to_dict(self) -> dict:
        return {
            "线索ID": self.lead_id,
            "姓名": self.name,
            "公司": self.company,
            "邮箱": self.email,
            "电话": self.phone,
            "状态": self.status,
            "标签": self.tags,
            "创建日期": self.created_at,
            "更新日期": self.updated_at,
        }


def _mask_contact_info(email: str, phone: str) -> tuple[str, str]:
    """对邮箱和电话进行部分脱敏（仅显示部分字符）。"""
    if "@" in email:
        parts = email.split("@")
        masked_email = parts[0][:2] + "***@" + parts[1]
    else:
        masked_email = email[:3] + "***"

    if len(phone) >= 7:
        masked_phone = phone[:3] + "****" + phone[-4:]
    else:
        masked_phone = phone[:2] + "***"

    return masked_email, masked_phone


def _validate_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def create_lead(name: str, company: str, email: str, phone: str,
                tags: list[str] | None = None) -> CRMRecord:
    """创建新线索记录。"""
    lead_id = "LD-" + uuid.uuid4().hex[:8].upper()
    # 清洗输入
    name = re.sub(r'[<>"\']', '', name)[:50]
    company = re.sub(r'[<>"\']', '', company)[:100]

    record = CRMRecord(
        lead_id=lead_id,
        name=name,
        company=company,
        email=email,
        phone=phone,
        status="new",
        tags=tags or [],
    )
    _leads_db[lead_id] = record.to_dict()
    return record


def update_lead_status(lead_id: str, new_status: str) -> dict:
    """更新线索状态。"""
    valid_statuses = {"new", "contacted", "qualified", "proposal", "closed_won", "closed_lost"}
    if new_status not in valid_statuses:
        return {"success": False, "message": f"无效状态: {new_status}，有效值: {valid_statuses}"}

    if lead_id not in _leads_db:
        return {"success": False, "message": f"线索 {lead_id} 不存在"}

    _leads_db[lead_id]["状态"] = new_status
    _leads_db[lead_id]["更新日期"] = str(date.today())
    _log_activity(lead_id, "status_update", f"状态更新为: {new_status}")
    return {"success": True, "lead_id": lead_id, "new_status": new_status}


def log_activity(lead_id: str, activity_type: str, notes: str) -> dict:
    """记录销售活动（电话/邮件/拜访）。"""
    _log_activity(lead_id, activity_type, notes)
    return {"success": True, "lead_id": lead_id, "activity": activity_type}


def _log_activity(lead_id: str, activity_type: str, notes: str) -> None:
    """内部记录活动日志。"""
    _activities_db.append({
        "lead_id": lead_id,
        "type": activity_type,
        "notes": notes[:500],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })


def get_lead(lead_id: str) -> dict | None:
    """获取线索详情。"""
    return _leads_db.get(lead_id)


def list_leads_by_status(status: str) -> list[dict]:
    """按状态筛选线索。"""
    return [r for r in _leads_db.values() if r.get("状态") == status]


def get_activities(lead_id: str) -> list[dict]:
    """获取线索的活动记录。"""
    return [a for a in _activities_db if a.get("lead_id") == lead_id]


def pipeline_summary() -> dict:
    """生成销售漏斗摘要。"""
    summary: dict[str, int] = {}
    for record in _leads_db.values():
        status = record.get("状态", "unknown")
        summary[status] = summary.get(status, 0) + 1
    return {
        "total": len(_leads_db),
        "by_status": summary,
        "activities_count": len(_activities_db),
    }
