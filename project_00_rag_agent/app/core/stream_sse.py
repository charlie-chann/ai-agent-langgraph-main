"""
core/stream_sse.py — SSE 格式化与 WAL 断点续推消费

【职责】
1. 将 WAL StreamEvent 格式化为标准 SSE（含 id 字段供 Last-Event-ID）
2. async 轮询 WAL，支持生成进行中续推
3. 客户端断开时按配置 cancel 或继续后台写 WAL
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Optional

from app.core.config import settings
from app.core.streaming import CancelToken
from app.infrastructure.persistence.stream_wal import StreamEvent, get_stream_status, read_events


def parse_last_event_id(header_value: Optional[str]) -> int:
    if not header_value:
        return 0
    try:
        return int(header_value.strip())
    except ValueError:
        return 0


def format_sse(event: StreamEvent, *, extra: Optional[dict] = None) -> str:
    data = event.to_sse_data()
    if extra and event.event_type == "meta":
        payload = {**event.payload, **extra}
        data = json.dumps(payload, ensure_ascii=False)
    lines = [f"id: {event.offset}", f"data: {data}"]
    return "\n".join(lines) + "\n\n"


async def consume_wal_sse(
    stream_id: str,
    *,
    after_offset: int = 0,
    extra_meta: Optional[dict] = None,
    cancel: Optional[CancelToken] = None,
) -> AsyncGenerator[str, None]:
    """
    从 WAL 读取并 yield SSE 块；生成未完成时轮询直到 complete/error/cancelled。
    """
    seen = after_offset
    poll = settings.stream_resume_poll_seconds
    loop = asyncio.get_running_loop()
    deadline = loop.time() + poll if poll > 0 else None

    while True:
        if cancel and cancel.is_cancelled:
            break

        events = read_events(stream_id, after_offset=seen)
        for ev in events:
            if cancel and cancel.is_cancelled:
                return
            if ev.event_type == "meta" and extra_meta:
                yield format_sse(ev, extra=extra_meta)
            elif ev.event_type == "token":
                yield format_sse(ev)
            elif ev.event_type == "meta":
                yield format_sse(ev)
            elif ev.event_type == "error":
                yield format_sse(ev)
            elif ev.event_type == "done":
                yield format_sse(ev)
            seen = ev.offset

        status = get_stream_status(stream_id) or {}
        st = status.get("status")
        if st in ("complete", "error", "cancelled"):
            break
        if deadline and loop.time() >= deadline:
            break
        await asyncio.sleep(0.05)
