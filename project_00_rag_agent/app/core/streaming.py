"""
core/streaming.py — 流式输出节流与资源清理

【职责】
1. token batch flush：按字符数 / 时间间隔合并推送，降低 SSE 与 CPU 开销
2. StreamBuffer：统一管理 buffer，支持 disconnect 时 flush 或 clear
3. CancelToken：客户端断开时通知上游停止（可选，与 stream_resume 配合）
"""
from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, AsyncIterator, Optional

from app.core.config import settings


class CancelToken:
    """轻量取消令牌；disconnect 或超时后 set，上游 generator 应检查并退出。"""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise asyncio.CancelledError("stream consumer disconnected")


async def batched_tokens(
    source: AsyncIterator[str],
    *,
    flush_chars: Optional[int] = None,
    flush_interval_ms: Optional[int] = None,
    cancel: Optional[CancelToken] = None,
) -> AsyncGenerator[str, None]:
    """
    将细粒度 token 合并为 batch 再 yield。

    - flush_chars：缓冲满 N 字符即 flush（默认 settings.stream_flush_chars）
    - flush_interval_ms：距上次 flush 超过 N ms 也 flush（默认 settings.stream_flush_interval_ms）
    """
    chars = flush_chars if flush_chars is not None else settings.stream_flush_chars
    interval_ms = flush_interval_ms if flush_interval_ms is not None else settings.stream_flush_interval_ms
    buf = ""
    last_flush = time.monotonic()

    async for token in source:
        if cancel and cancel.is_cancelled:
            break
        if not token:
            continue
        # META 事件不参与 batch，避免与 answer token 粘连
        if token.startswith("\n\n__META__"):
            if buf:
                yield buf
                buf = ""
                last_flush = time.monotonic()
            yield token
            continue
        buf += token
        now = time.monotonic()
        elapsed_ms = (now - last_flush) * 1000
        if len(buf) >= chars or elapsed_ms >= interval_ms:
            yield buf
            buf = ""
            last_flush = now

    if buf and not (cancel and cancel.is_cancelled):
        yield buf
