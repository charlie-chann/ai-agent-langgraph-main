"""知识库入库用例编排。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.infrastructure.cache.redis_cache import cache_delete_prefix
from app.retrieval.ingest import ingest_files


def ingest_paths(paths: List[Path], *, acl_roles: List[str]) -> dict:
    """执行文档入库并在成功后失效答案缓存。"""
    result = ingest_files(paths, acl_roles=acl_roles)
    cache_delete_prefix("rag:ask:")
    return result
