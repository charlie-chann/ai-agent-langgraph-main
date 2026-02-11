"""
metrics.py — 进程内 Prometheus 风格计数器（轻量骨架）

【职责】
1. 维护请求数、缓存命中、错误数、HITL 待审等核心指标的内存计数
2. 提供线程安全的 inc / snapshot 接口
3. 供 /metrics 端点或健康检查导出当前快照

【设计原因】
1. 不引入完整 prometheus_client 依赖，适合 demo / 小规模部署快速观测
2. threading.Lock 保证多 worker 线程下计数准确（单进程内）
3. inc 支持动态指标名，未预注册的 name 会从 0 开始累加
4. snapshot 返回 dict 副本，避免外部直接修改内部 _counters

【预置指标】
  requests_total — HTTP 请求总数
  cache_hits     — 缓存命中次数
  errors_total   — 业务/系统错误总数
  hitl_pending   — 当前待人工审批的 HITL 任务数（由业务增减）
"""
from __future__ import annotations

from threading import Lock

# 全局锁：保护 _counters 的并发读写
_lock = Lock()
# 指标名 → 累计值
_counters = {
    "requests_total": 0,
    "cache_hits": 0,
    "errors_total": 0,
    "hitl_pending": 0,
}


def inc(name: str, n: int = 1) -> None:
    """
    将指定指标增加 n（默认 1）。

    若 name 不在预置字典中，get(..., 0) 会从零开始计数。
    """
    with _lock:
        _counters[name] = _counters.get(name, 0) + n


def snapshot() -> dict:
    """
    返回当前所有指标的浅拷贝快照，供 /metrics 或监控采集使用。
    """
    with _lock:
        return dict(_counters)
