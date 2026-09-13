"""
storage/stream_wal.py — SSE 流式生成 WAL（Write-Ahead Log）

【职责】
1. 记录流式 token / meta / done 事件，支持 Last-Event-ID 断点续推
2. 优先 Redis Stream；不可用时降级进程内 dict
3. 幂等：同一 offset 只写一次；读侧按 offset 顺序回放

【设计原因】
1. 生成与推送解耦：即使 HTTP 断开，WAL 仍可保留已生成内容供重连
2. stream_id 通常 = request_id，与 conversation_id 组合定位一次问答
3. TTL 自动过期，避免 Redis / 内存无限增长
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any, List, Literal, Optional

from loguru import logger

from app.core.config import settings

StreamStatus = Literal["running", "complete", "error", "cancelled"]

_redis_client = None
_mem_lock = Lock()
# stream_id -> {"meta": dict, "events": list[tuple[int, dict]], "status": str, "expires": float}
_mem_streams: dict[str, dict] = {}


def _get_redis():
    """懒加载 Redis 客户端；不可用时返回 None 并降级内存。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.stream_resume_enabled:
        return None
    try:
        import redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        logger.info("Stream WAL Redis connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Stream WAL Redis unavailable, using in-memory: {e}")
        _redis_client = False
        return None


def _meta_key(stream_id: str) -> str:
    """构造流元数据的 Redis key。"""
    return f"rag:stream:{stream_id}:meta"


def _events_key(stream_id: str) -> str:
    """构造流事件列表的 Redis key。"""
    return f"rag:stream:{stream_id}:events"


def _ttl() -> int:
    """返回 WAL 过期秒数。"""
    return settings.stream_wal_ttl_seconds


@dataclass
class StreamEvent:
    offset: int
    event_type: str  # token | meta | done | error
    payload: dict

    def to_sse_data(self) -> str:
        """将事件序列化为 SSE data 字段内容。"""
        if self.event_type == "token":
            return json.dumps({"token": self.payload.get("token", "")}, ensure_ascii=False)
        if self.event_type == "meta":
            return json.dumps(self.payload, ensure_ascii=False)
        if self.event_type == "done":
            return "[DONE]"
        return json.dumps(self.payload, ensure_ascii=False)


def _counter_key(stream_id: str) -> str:
    """构造流事件 offset 计数器的 Redis key。"""
    return f"rag:stream:{stream_id}:counter"


def begin_stream(stream_id: str, *, conversation_id: str, request_id: str, message: str) -> None:
    """初始化一次流式会话 WAL。"""
    if not settings.stream_resume_enabled:
        return
    meta = {
        "stream_id": stream_id,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "message": message[:500],
        "status": "running",
        "created_at": time.time(),
    }
    r = _get_redis()
    if r and r is not False:
        try:
            pipe = r.pipeline()
            pipe.setex(_meta_key(stream_id), _ttl(), json.dumps(meta, ensure_ascii=False))
            pipe.delete(_events_key(stream_id))
            pipe.set(_counter_key(stream_id), 0)
            pipe.expire(_counter_key(stream_id), _ttl())
            pipe.execute()
            return
        except Exception as e:
            logger.warning(f"Stream WAL begin failed (redis): {e}")
    with _mem_lock:
        _mem_streams[stream_id] = {
            "meta": meta,
            "events": [],
            "next_offset": 0,
            "expires": time.time() + _ttl(),
        }


def append_event(stream_id: str, event_type: str, payload: dict) -> int:
    """
    追加一条 WAL 事件，返回 monotonic offset（从 1 开始）。

    供 SSE `id:` 字段与 Last-Event-ID 对齐。
    """
    if not settings.stream_resume_enabled:
        return 0
    event = {"type": event_type, "payload": payload, "ts": time.time()}
    r = _get_redis()
    if r and r is not False:
        try:
            offset = int(r.incr(_counter_key(stream_id)))
            r.expire(_counter_key(stream_id), _ttl())
            row = json.dumps({"offset": offset, **event}, ensure_ascii=False)
            r.rpush(_events_key(stream_id), row)
            r.expire(_events_key(stream_id), _ttl())
            return offset
        except Exception as e:
            logger.warning(f"Stream WAL append failed (redis): {e}")
    with _mem_lock:
        entry = _mem_streams.get(stream_id)
        if not entry:
            return 0
        entry["next_offset"] = entry.get("next_offset", 0) + 1
        offset = entry["next_offset"]
        entry["events"].append((offset, event))
        entry["expires"] = time.time() + _ttl()
        return offset


def finalize_stream(stream_id: str, *, status: StreamStatus = "complete", error: Optional[str] = None) -> None:
    """标记流结束状态（complete / error / cancelled）。"""
    if not settings.stream_resume_enabled:
        return
    r = _get_redis()
    if r and r is not False:
        try:
            meta_raw = r.get(_meta_key(stream_id))
            if meta_raw:
                meta = json.loads(meta_raw)
                meta["status"] = status
                if error:
                    meta["error"] = error
                meta["finished_at"] = time.time()
                r.setex(_meta_key(stream_id), _ttl(), json.dumps(meta, ensure_ascii=False))
            return
        except Exception as e:
            logger.warning(f"Stream WAL finalize failed (redis): {e}")
    with _mem_lock:
        entry = _mem_streams.get(stream_id)
        if entry:
            entry["meta"]["status"] = status
            if error:
                entry["meta"]["error"] = error
            entry["meta"]["finished_at"] = time.time()


def get_stream_status(stream_id: str) -> Optional[dict]:
    """读取流元数据与状态；过期或不存在返回 None。"""
    if not settings.stream_resume_enabled:
        return None
    r = _get_redis()
    if r and r is not False:
        try:
            raw = r.get(_meta_key(stream_id))
            return json.loads(raw) if raw else None
        except Exception:
            return None
    with _mem_lock:
        entry = _mem_streams.get(stream_id)
        if not entry:
            return None
        if time.time() > entry.get("expires", 0):
            del _mem_streams[stream_id]
            return None
        return dict(entry["meta"])


def read_events(stream_id: str, *, after_offset: int = 0) -> List[StreamEvent]:
    """读取 offset > after_offset 的全部事件（用于断线续推）。"""
    if not settings.stream_resume_enabled:
        return []
    out: List[StreamEvent] = []
    r = _get_redis()
    if r and r is not False:
        try:
            rows = r.lrange(_events_key(stream_id), 0, -1)
            for row in rows:
                data = json.loads(row)
                off = int(data.get("offset", 0))
                if off <= after_offset:
                    continue
                out.append(
                    StreamEvent(
                        offset=off,
                        event_type=data.get("type", "token"),
                        payload=data.get("payload") or {},
                    )
                )
            return sorted(out, key=lambda e: e.offset)
        except Exception as e:
            logger.warning(f"Stream WAL read failed (redis): {e}")
            return []
    with _mem_lock:
        entry = _mem_streams.get(stream_id)
        if not entry:
            return []
        for off, ev in entry.get("events", []):
            if off <= after_offset:
                continue
            out.append(StreamEvent(offset=off, event_type=ev["type"], payload=ev.get("payload") or {}))
        return sorted(out, key=lambda e: e.offset)


def wait_for_events(
    stream_id: str,
    *,
    after_offset: int,
    timeout_seconds: float = 30.0,
    poll_interval: float = 0.05,
) -> List[StreamEvent]:
    """
    阻塞等待新事件（续推时生成仍在进行）。

    简单轮询 WAL；生产可换 Redis BLOCK XREAD。
    """
    deadline = time.time() + timeout_seconds
    seen = after_offset
    collected: List[StreamEvent] = []
    while time.time() < deadline:
        batch = read_events(stream_id, after_offset=seen)
        if batch:
            collected.extend(batch)
            seen = batch[-1].offset
            status = get_stream_status(stream_id) or {}
            if status.get("status") in ("complete", "error", "cancelled"):
                break
        else:
            status = get_stream_status(stream_id) or {}
            if status.get("status") in ("complete", "error", "cancelled"):
                break
        time.sleep(poll_interval)
    return collected
