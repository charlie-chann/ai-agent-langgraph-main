"""文档入库相关 Schema。"""
from __future__ import annotations

from pydantic import BaseModel


class IngestResponse(BaseModel):
    files_loaded: int
    chunks_created: int
    documents_indexed: int = 0
    kg_triples: int = 0
    error_count: int = 0
