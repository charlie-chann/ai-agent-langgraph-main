# tools/log_analyzer.py — 日志分析与故障根因工具
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from config import MAX_LOG_LINES, ERROR_KEYWORDS, WARNING_KEYWORDS, TICKET_PREFIX


@dataclass
class LogEvent:
    """日志事件。"""
    timestamp: str
    level: str       # ERROR | WARN | INFO | DEBUG
    service: str
    message: str
    raw_line: str


@dataclass
class RCAReport:
    """根因分析报告。"""
    ticket_id: str
    severity: str         # "critical" | "major" | "minor"
    root_cause: str
    affected_services: list[str]
    error_count: int
    warning_count: int
    timeline: list[dict]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return {
            "工单ID": self.ticket_id,
            "严重程度": self.severity,
            "根因分析": self.root_cause,
            "受影响服务": self.affected_services,
            "错误数": self.error_count,
            "警告数": self.warning_count,
            "时间线": self.timeline,
            "处理建议": self.recommendations,
        }


_LOG_PATTERN = re.compile(
    r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})?'
    r'\s*'
    r'(?P<level>ERROR|FATAL|CRITICAL|WARN(?:ING)?|INFO|DEBUG)?'
    r'\s*'
    r'(?:\[(?P<service>[^\]]+)\])?\s*'
    r'(?P<message>.+)$',
    re.IGNORECASE,
)


def parse_logs(log_text: str) -> list[LogEvent]:
    """解析日志文本，提取结构化事件。"""
    events = []
    lines = log_text.strip().split('\n')[:MAX_LOG_LINES]

    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = _LOG_PATTERN.match(line)
        if not m:
            continue
        level = (m.group("level") or "INFO").upper()
        if level == "WARNING":
            level = "WARN"
        if level in ("FATAL",):
            level = "ERROR"
        events.append(LogEvent(
            timestamp=m.group("timestamp") or "",
            level=level,
            service=m.group("service") or "unknown",
            message=(m.group("message") or line)[:500],
            raw_line=line[:300],
        ))
    return events


def _detect_root_cause(errors: list[LogEvent]) -> str:
    """根据错误模式推断根因。"""
    messages = " ".join(e.message for e in errors).lower()

    if "out of memory" in messages or "oom" in messages:
        return "内存不足（OOM），进程被系统终止"
    if "database" in messages and ("timeout" in messages or "error" in messages or "connection" in messages):
        return "数据库连接或查询超时"
    if "connection refused" in messages or "connection timeout" in messages:
        return "网络连接失败，下游服务不可达"
    if "disk full" in messages or "no space" in messages:
        return "磁盘空间耗尽"
    if "permission denied" in messages or "403" in messages:
        return "权限不足，服务账号缺少必要权限"
    if "null pointer" in messages or "nullpointerexception" in messages:
        return "空指针引用，代码逻辑缺陷"
    if "timeout" in messages:
        return "服务超时，可能是高负载或资源竞争"
    if "traceback" in messages or "exception" in messages:
        return "应用代码异常，需检查堆栈跟踪"
    if errors:
        return f"检测到 {len(errors)} 个错误事件，需人工确认根因"
    return "未检测到明显错误，系统运行正常"


def analyze_logs(log_text: str) -> RCAReport:
    """
    分析日志文本，生成根因分析报告。

    Args:
        log_text: 原始日志文本

    Returns:
        RCAReport
    """
    events = parse_logs(log_text)
    errors = [e for e in events if e.level in ("ERROR", "CRITICAL")]
    warnings = [e for e in events if e.level == "WARN"]

    affected = list(dict.fromkeys(e.service for e in errors if e.service != "unknown"))

    # 严重程度判断
    if len(errors) >= 10:
        severity = "critical"
    elif len(errors) >= 3:
        severity = "major"
    elif errors:
        severity = "minor"
    else:
        severity = "minor"

    root_cause = _detect_root_cause(errors)

    # 时间线（取前10个错误事件）
    timeline = [
        {"时间": e.timestamp, "服务": e.service, "事件": e.message[:100]}
        for e in errors[:10]
    ]

    # 处理建议
    recommendations = []
    if "OOM" in root_cause or "内存" in root_cause:
        recommendations.append("增加服务内存配额或优化内存使用")
        recommendations.append("检查是否存在内存泄漏")
    if "数据库" in root_cause:
        recommendations.append("检查数据库连接池配置")
        recommendations.append("分析慢查询日志")
    if "权限" in root_cause:
        recommendations.append("检查服务账号权限配置")
    if not recommendations:
        recommendations.append("查看完整堆栈跟踪，定位具体代码位置")
        recommendations.append("检查最近发布的变更")

    ticket_id = f"{TICKET_PREFIX}-{uuid.uuid4().hex[:6].upper()}"

    return RCAReport(
        ticket_id=ticket_id,
        severity=severity,
        root_cause=root_cause,
        affected_services=affected,
        error_count=len(errors),
        warning_count=len(warnings),
        timeline=timeline,
        recommendations=recommendations,
    )
