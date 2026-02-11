"""
cache.py — Redis 缓存层（内存降级）

【职责】
1. 为 RAG 查询结果等热点数据提供 TTL 缓存
2. 优先使用 Redis；连接失败时自动降级到进程内 dict
3. 提供 cache_key / cache_get / cache_set / cache_delete_prefix 统一接口

【设计原因】
1. 双后端策略：生产环境 Redis 可跨实例共享；开发/单机无 Redis 时仍可运行
2. cache_key 对 payload 做 SHA256 摘要，避免 key 过长且保证相同输入命中同一 key
3. _redis_client = False 作为「已尝试连接但失败」的哨兵值，避免反复 ping Redis
4. 内存缓存带过期时间戳，与 Redis TTL 语义一致

【Key 命名规范】
  rag:{prefix}:{16位hex摘要}
  例如：rag:chat:a1b2c3d4e5f67890
"""
from __future__ import annotations

import hashlib
import json
import time
from threading import Lock
from typing import Any, Optional

from loguru import logger

from app.core.config import settings

# 懒加载 Redis 客户端；None=未初始化，False=连接失败哨兵
_redis_client = None
# 内存降级：key → (value, expires_at_unix)
_mem_cache: dict[str, tuple[Any, float]] = {}
_mem_lock = Lock()


def _get_redis():
    """
    获取 Redis 连接（单例懒加载）。

    - cache_enabled=False 时直接返回 None
    - 首次连接成功则缓存 client
    - 连接异常则置 _redis_client=False 并降级内存
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.cache_enabled:
        return None
    try:
        import redis

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis cache connected")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, using in-memory cache: {e}")
        _redis_client = False  # sentinel: tried and failed
        return None


def cache_key(prefix: str, payload: dict) -> str:
    """
    根据 prefix 与 payload 生成确定性缓存 key。

    sort_keys=True 保证 dict 键序不影响摘要；取 SHA256 前 16 位缩短 key 长度。
    """
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"{settings.cache_namespace}:{prefix}:{digest}"


def cache_get(key: str) -> Optional[Any]:
    """
    读取缓存；未命中或已过期返回 None。

    优先 Redis GET + JSON 反序列化；失败或未启用时查内存 dict 并检查 expires。
    """
    if not settings.cache_enabled:
        return None
    r = _get_redis()
    if r and r is not False:
        try:
            val = r.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
    with _mem_lock:
        entry = _mem_cache.get(key)
        if not entry:
            return None
        val, expires = entry
        if time.time() > expires:
            del _mem_cache[key]
            return None
        return val


def cache_set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """
    写入缓存，默认 TTL 来自 settings.cache_ttl_seconds。

    Redis 使用 SETEX；内存路径存储 (value, now+ttl)。
    """
    if not settings.cache_enabled:
        return
    ttl = ttl or settings.cache_ttl_seconds
    r = _get_redis()
    if r and r is not False:
        try:
            r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            return
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
    with _mem_lock:
        _mem_cache[key] = (value, time.time() + ttl)


def cache_delete_prefix(prefix: str) -> None:
    """
    按前缀批量删除缓存（如 ingest 后清空 rag:chat:*）。

    Redis 用 scan_iter 避免 KEYS 阻塞；内存侧遍历 dict 删除匹配 key。
    """
    r = _get_redis()
    if r and r is not False:
        try:
            for key in r.scan_iter(f"{prefix}*"):
                r.delete(key)
        except Exception:
            pass
    with _mem_lock:
        to_del = [k for k in _mem_cache if k.startswith(prefix)]
        for k in to_del:
            del _mem_cache[k]
