"""
request_context.py — 请求上下文与 request_id 传播

【职责】
1. 为每个 HTTP 请求生成唯一 request_id
2. 通过 ContextVar 在异步调用链中传递 request_id（无需显式参数透传）
3. 供日志、错误响应、链路追踪统一关联同一请求

【设计原因】
1. ContextVar 与 asyncio 兼容：同一请求内的协程共享变量，不同请求隔离
2. uuid4 hex 取前 12 位：足够唯一且日志中更易读
3. get_request_id 在无上下文时返回 "unknown"，避免空字符串导致排查困难

【典型用法】
  中间件入口：new_request_id()
  异常处理/日志：get_request_id()
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar

# 当前请求的 request_id；默认空字符串表示尚未设置
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    """
    生成新的 request_id，写入 ContextVar 并返回。

    应在请求进入时（如 FastAPI 中间件）调用一次。
    """
    rid = uuid.uuid4().hex[:12]
    request_id_var.set(rid)
    return rid


def get_request_id() -> str:
    """
    读取当前上下文中的 request_id；未设置时返回 "unknown"。
    """
    return request_id_var.get() or "unknown"
