"""
rate_limit.py — 请求限流（Redis 计数 + 内存滑动窗口降级）

【职责】
1. 按用户标识（X-User-Id 或客户端 IP）限制单位时间内的请求次数
2. 提供 check_rate_limit 供业务直接调用
3. 提供 rate_limit_middleware 作为 FastAPI HTTP 中间件

【设计原因】
1. Redis 路径：INCR + EXPIRE 实现固定窗口计数，简单且原子
2. 内存路径：滑动窗口（保留 window 内时间戳列表），比固定窗口更平滑
3. 健康检查、文档、登录等路径白名单，避免探针或拿 token 被限流
4. 超限返回 429 并带 Retry-After 头，便于客户端退避

【限流参数】
  rate_limit_requests       — 窗口内最大请求数（默认 60）
  rate_limit_window_seconds — 窗口长度秒数（默认 60）
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request, status
from loguru import logger

from app.core.config import settings

# 懒加载 Redis；False 表示连接失败，后续走内存限流
_redis_client = None
# 内存滑动窗口：key → 该 key 在窗口内的请求时间戳列表
_mem_buckets: dict[str, list[float]] = {}
_mem_lock = Lock()


def _get_redis():
    """获取 Redis 连接（单例）；失败时置哨兵 False 并返回 None。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis rate limit fallback to memory: {e}")
        _redis_client = False
        return None


def _mem_check(key: str, limit: int, window: int) -> bool:
    """
    内存滑动窗口限流检查。

    1. 剔除 window 秒之前的旧时间戳
    2. 若当前计数 >= limit 返回 False（拒绝）
    3. 否则记录本次时间戳并返回 True（放行）
    """
    now = time.time()
    with _mem_lock:
        bucket = _mem_buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


def check_rate_limit(identifier: str) -> None:
    """
    对 identifier 执行限流；超限抛出 HTTP 429。

    Redis 策略：pipeline INCR + EXPIRE，count > limit 则拒绝。
    Redis 异常时降级到 _mem_check，行为与配置 limit/window 一致。
    """
    limit = settings.rate_limit_requests
    window = settings.rate_limit_window_seconds
    key = f"rl:{identifier}"

    r = _get_redis()
    if r and r is not False:
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            count, _ = pipe.execute()
            if int(count) > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(window)},
                )
            return
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limit error: {e}")

    if not _mem_check(key, limit, window):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(window)},
        )


async def rate_limit_middleware(request: Request, call_next):
    """
    FastAPI HTTP 中间件：除白名单路径外，对每个请求做限流后 call_next。

    标识优先级：X-User-Id 请求头 > 客户端 IP > "anon"
    """
    if request.url.path in ("/health", "/ready", "/metrics", "/auth/token", "/docs", "/openapi.json"):
        return await call_next(request)
    user_key = request.headers.get("X-User-Id") or request.client.host if request.client else "anon"
    check_rate_limit(user_key)
    return await call_next(request)
