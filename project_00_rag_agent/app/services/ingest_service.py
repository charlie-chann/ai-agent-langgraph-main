"""知识库入库用例编排。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from app.infrastructure.cache.redis_cache import cache_delete_prefix
from app.knowledge.ingest import ingest_files, sanitize_filename, validate_upload


def save_upload(filename: str, content: bytes, tmp_dir: Path) -> Path:
    """校验上传文件并写入临时目录，返回安全路径。"""
    tmp_dir.mkdir(exist_ok=True)
    validate_upload(filename, len(content))
    safe_name = sanitize_filename(filename)
    dest = tmp_dir / safe_name
    dest.write_bytes(content)
    return dest


def ingest_paths(paths: List[Path], *, acl_roles: List[str]) -> dict:
    """执行文档入库并在成功后失效答案缓存。"""
    result = ingest_files(paths, acl_roles=acl_roles)
    cache_delete_prefix(f"{settings.cache_namespace}:ask:")
    return result
