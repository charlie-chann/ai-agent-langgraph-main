# tools/appointment_tool.py — 预约管理工具
from __future__ import annotations
import uuid
import re
from dataclasses import dataclass, field
from datetime import date, timedelta


# 内存中的预约存储（生产环境应替换为数据库）
_appointments: dict[str, dict] = {}

# 科室对应的默认出诊日（0=周一...6=周日，最多等待14天）
_DEPT_AVAILABLE_DAYS: dict[str, list[int]] = {
    "急诊":    [0, 1, 2, 3, 4, 5, 6],   # 全周
    "内科":    [0, 1, 2, 3, 4],
    "外科":    [0, 1, 2, 3, 4],
    "骨科":    [1, 3, 4],
    "心内科":  [1, 2, 4],
    "神经内科": [0, 3, 4],
    "消化科":  [1, 2, 5],
    "呼吸科":  [2, 4],
    "内分泌科": [1, 4],
    "皮肤科":  [0, 3, 5],
    "眼科":    [2, 3, 5],
}


@dataclass
class Appointment:
    """预约记录数据类。"""
    appointment_id: str
    patient_id: str
    department: str
    appointment_date: str
    status: str = "confirmed"        # confirmed | cancelled | completed
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "预约编号": self.appointment_id,
            "患者ID": self.patient_id,
            "就诊科室": self.department,
            "预约日期": self.appointment_date,
            "状态": self.status,
            "备注": self.notes,
        }


def _next_available_date(department: str, from_date: date | None = None) -> date:
    """计算指定科室的最近可预约日期。"""
    if from_date is None:
        from_date = date.today()
    available_days = _DEPT_AVAILABLE_DAYS.get(department, [0, 1, 2, 3, 4])
    for delta in range(1, 30):
        candidate = from_date + timedelta(days=delta)
        if candidate.weekday() in available_days:
            return candidate
    return from_date + timedelta(days=7)


def _anonymize_patient_id(raw_id: str) -> str:
    """确保患者 ID 不含敏感信息（仅保留字母数字）。"""
    clean = re.sub(r'[^A-Za-z0-9]', '', raw_id)
    if len(clean) > 16:
        clean = clean[:16]
    elif len(clean) < 4:
        clean = clean + "ANON"
    return clean.upper()


def book_appointment(patient_id: str, department: str, preferred_date: str | None = None,
                     notes: str = "") -> Appointment:
    """
    为患者预约指定科室门诊。

    Args:
        patient_id: 患者ID（会自动匿名化）
        department: 就诊科室
        preferred_date: 优先预约日期（格式 YYYY-MM-DD），可选
        notes: 预约备注

    Returns:
        Appointment: 预约确认信息
    """
    clean_id = _anonymize_patient_id(patient_id)

    if preferred_date:
        try:
            from_date = date.fromisoformat(preferred_date)
        except ValueError:
            from_date = date.today()
    else:
        from_date = date.today()

    appt_date = _next_available_date(department, from_date)
    appt_id = "APT-" + uuid.uuid4().hex[:8].upper()

    appt = Appointment(
        appointment_id=appt_id,
        patient_id=clean_id,
        department=department,
        appointment_date=str(appt_date),
        notes=notes[:200],   # 截断防止超长
    )
    _appointments[appt_id] = appt.to_dict()
    return appt


def cancel_appointment(appointment_id: str) -> dict:
    """取消预约，返回操作结果。"""
    appt_id = appointment_id.strip().upper()
    if appt_id not in _appointments:
        return {"success": False, "message": f"未找到预约 {appt_id}"}
    _appointments[appt_id]["状态"] = "cancelled"
    return {"success": True, "message": f"预约 {appt_id} 已取消"}


def query_appointment(appointment_id: str) -> dict | None:
    """查询预约详情。"""
    return _appointments.get(appointment_id.strip().upper())


def list_appointments() -> list[dict]:
    """列出所有预约记录。"""
    return list(_appointments.values())
