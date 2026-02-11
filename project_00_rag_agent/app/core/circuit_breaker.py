"""
core/circuit_breaker.py — LLM / Embedding 调用熔断器

【职责】
在 Provider 连续失败达到阈值时「开路」，快速失败避免雪崩；
经过 recovery_timeout 后进入半开状态，允许下一次调用试探恢复。

【设计原因】
1. 外部 LLM/Embedding 服务不稳定时，若不熔断会导致线程堆积、超时级联
2. 线程锁保证多 worker / 异步场景下 failure 计数与 open 状态一致
3. 模块级单例 llm_breaker / embed_breaker，供 factory 与 get_stats 统一查询

【与 project_01 差异】
project_01 无熔断层；本模块为 project_00 新增，配合 config.cb_* 与 providers.factory 使用。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock

from loguru import logger

from app.core.config import settings


@dataclass
class CircuitBreaker:
    """
    简易熔断器实现（Closed → Open → Half-Open → Closed）。

    - Closed：正常调用，失败计数累加
    - Open：is_open() 为 True，调用方应直接拒绝或返回 503
    - Half-Open：超过 recovery_timeout 后自动重置 failures，允许试探一次
    """

    name: str
    failure_threshold: int = settings.cb_failure_threshold
    recovery_timeout: float = settings.cb_recovery_timeout
    _failures: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def is_open(self) -> bool:
        """
        判断熔断器是否处于开路（拒绝调用）状态。

        若已开路且超过 recovery_timeout，则重置为半开/关闭并返回 False。
        """
        with self._lock:
            if self._opened_at is None:
                return False
            # Recovery 窗口到期：清零失败计数，允许下一次调用试探
            if time.time() - self._opened_at >= self.recovery_timeout:
                logger.info(f"Circuit {self.name}: half-open, resetting")
                self._failures = 0
                self._opened_at = None
                return False
            return True

    def record_success(self) -> None:
        """记录一次成功调用，重置失败计数并关闭熔断。"""
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        """
        记录一次失败；连续失败达到 failure_threshold 时触发开路。
        """
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.time()
                logger.error(f"Circuit {self.name}: OPEN after {self._failures} failures")

    def status(self) -> dict:
        """返回可序列化的运行态，供 get_stats / 监控使用。"""
        return {
            "name": self.name,
            "open": self.is_open(),
            "failures": self._failures,
        }


# ── 模块级单例 ────────────────────────────────────────────────────────────────
# LLM 与 Embedding 分别熔断，避免 Embedding 故障拖死对话生成
llm_breaker = CircuitBreaker("llm")
embed_breaker = CircuitBreaker("embedding")
