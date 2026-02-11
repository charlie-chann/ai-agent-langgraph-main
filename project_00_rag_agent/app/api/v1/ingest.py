"""知识库入库路由。"""
from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import TokenPayload, require_permission
from app.schemas.ingest import IngestResponse
from app.services.ingest_service import ingest_paths, save_upload

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: List[UploadFile] = File(...),
    user: TokenPayload = Depends(require_permission("ingest")),
):
    tmp_dir = Path("/tmp/rag_uploads_v2")
    saved = []
    for f in files:
        content = await f.read()
        saved.append(save_upload(f.filename or "upload.txt", content, tmp_dir))

    result = ingest_paths(saved, acl_roles=[user.role, "public"])
    return IngestResponse(
        files_loaded=result.get("files_loaded", 0),
        chunks_created=result.get("chunks_created", 0),
        documents_indexed=result.get("documents_indexed", 0),
        kg_triples=result.get("kg_triples", 0),
        error_count=result.get("error_count", 0),
    )
