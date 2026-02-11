"""知识库入库路由。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import TokenPayload, require_permission
from app.infrastructure.cache.redis_cache import cache_delete_prefix
from app.retrieval.ingest import ingest_files, sanitize_filename, validate_upload
from app.schemas.ingest import IngestResponse

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: List[UploadFile] = File(...),
    user: TokenPayload = Depends(require_permission("ingest")),
):
    tmp_dir = Path("/tmp/rag_uploads_v2")
    tmp_dir.mkdir(exist_ok=True)
    saved = []
    for f in files:
        content = await f.read()
        validate_upload(f.filename or "upload.txt", len(content))
        safe_name = sanitize_filename(f.filename or "upload.txt")
        dest = tmp_dir / safe_name
        dest.write_bytes(content)
        saved.append(dest)

    result = ingest_files(saved, acl_roles=[user.role, "public"])
    cache_delete_prefix("rag:ask:")
    return IngestResponse(
        files_loaded=result.get("files_loaded", 0),
        chunks_created=result.get("chunks_created", 0),
        documents_indexed=result.get("documents_indexed", 0),
        kg_triples=result.get("kg_triples", 0),
        error_count=result.get("error_count", 0),
    )
