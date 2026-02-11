"""
tools/ingest.py — 安全文档摄入流水线（含 KG 抽取）

【职责】
把用户上传的原始文件（PDF/TXT/MD/DOCX）转化为可检索的向量索引，并可选写入知识图谱。

【完整流程】
  校验文件名/大小 → 加载文件 → 切分 chunk → 写入 ChromaDB + BM25
  → （可选）规则/LLM 混合抽取三元组 → 持久化 KG

【设计原因】
1. 按文件类型映射 Loader：不同格式用 LangChain 社区最合适的解析器
2. RecursiveCharacterTextSplitter：优先按段落/句号切，中文友好
3. sanitize_filename + validate_upload：防止路径穿越与超大文件拖垮服务
4. acl_roles 写入 metadata：后续 retriever 按 JWT 角色做 ACL 过滤
5. ingest 与 retriever 分离：摄入只负责「写」，检索只负责「读」，职责清晰
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredMarkdownLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from config import settings, CHUNK_SIZE, CHUNK_OVERLAP
from app.retrieval.knowledge_graph import ingest_chunks_to_kg
from app.retrieval.retriever import build_vectorstore, get_vectorstore, set_chunks

# 文件扩展名 → Loader 类 的映射表
# 新增格式时只需在此注册，无需改 load_documents 主逻辑
LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
    ".markdown": UnstructuredMarkdownLoader,
    ".docx": Docx2txtLoader,
}

# 单文件大小上限，防止恶意大文件耗尽内存/磁盘
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20MB


def sanitize_filename(name: str) -> str:
    """
    清洗上传文件名，只保留 basename 并替换非法字符。

    防止 ../../etc/passwd 类路径穿越；过长文件名截断至 200 字符。
    """
    name = Path(name).name
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "upload.bin"


def load_documents(file_paths: List[str | Path], acl_roles: Optional[List[str]] = None) -> List[Document]:
    """
    从磁盘加载一个或多个文件，返回 LangChain Document 列表。

    每个 Document 包含：
      - page_content：文本正文
      - metadata：source、doc_id、acl_roles、loaded_at 等（用于溯源与 ACL）

    单个文件失败不会中断整批，失败的文件记日志并跳过。
    """
    docs: List[Document] = []
    roles = acl_roles or ["public"]
    for fp in file_paths:
        fp = Path(fp)
        suffix = fp.suffix.lower()
        loader_cls = LOADER_MAP.get(suffix)
        if loader_cls is None:
            logger.warning(f"Unsupported: {fp.name}")
            continue
        try:
            loaded = loader_cls(str(fp)).load()
            doc_id = str(uuid.uuid4())[:8]
            for doc in loaded:
                doc.metadata.setdefault("source", fp.name)
                doc.metadata["loaded_at"] = datetime.now().isoformat()
                doc.metadata["doc_id"] = doc_id
                doc.metadata["acl_roles"] = roles
                doc.metadata.setdefault("doc_type", "general")
            docs.extend(loaded)
        except Exception as e:
            logger.error(f"Load failed {fp}: {e}")
    return docs


def split_documents(docs: List[Document]) -> List[Document]:
    """
    将长文档切分为较小 chunk，便于向量检索精准命中。

    【为什么需要切分】
    LLM 上下文有限，不可能把整本书塞进 Prompt；检索也需要「段落级」粒度。

    【分隔符优先级】
    先按双换行（段落）→ 单换行 → 中文句号等切，尽量保持语义完整。

    add_start_index=True：记录 chunk 在原文中的起始位置，便于溯源。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    for i, c in enumerate(chunks):
        c.metadata["chunk_index"] = i
        c.metadata["total_chunks"] = len(chunks)
    return chunks


def ingest_files(
    file_paths: List[str | Path],
    *,
    force_rebuild: bool = False,
    acl_roles: Optional[List[str]] = None,
) -> dict:
    """
    完整摄入流水线：load → split → build_vectorstore → （可选）KG 抽取。

    Args:
        file_paths: 待摄入文件路径列表
        force_rebuild: True 时删除旧 Chroma 集合并重建
        acl_roles: 写入 chunk metadata 的 ACL 角色列表

    Returns:
        统计 dict：files_loaded, chunks_created, documents_indexed, kg_triples, error_count
    """
    docs = load_documents(file_paths, acl_roles=acl_roles)
    if not docs:
        return {"files_loaded": 0, "chunks_created": 0, "kg_triples": 0, "error_count": 1}

    chunks = split_documents(docs)
    try:
        build_vectorstore(chunks, force_rebuild=force_rebuild)
        doc_count = get_vectorstore()._collection.count()
    except Exception as e:
        logger.error(f"Vectorstore failed: {e}")
        return {"files_loaded": len(docs), "chunks_created": len(chunks), "error_count": 1, "error": str(e)}

    kg_count = 0
    if settings.kg_enabled:
        kg_count = ingest_chunks_to_kg(chunks)

    return {
        "files_loaded": len(docs),
        "chunks_created": len(chunks),
        "documents_indexed": doc_count,
        "kg_triples": kg_count,
        "error_count": 0,
    }


def validate_upload(filename: str, size: int) -> None:
    """
    上传前校验：扩展名必须在 LOADER_MAP 内，且文件不超过 MAX_FILE_BYTES。

    不通过时抛出 ValidationError，由 API 层转为 4xx 响应。
    """
    from app.core.exceptions import ValidationError

    safe = sanitize_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in LOADER_MAP:
        raise ValidationError(f"Unsupported file type: {suffix}")
    if size > MAX_FILE_BYTES:
        raise ValidationError(f"File too large: {size} bytes (max {MAX_FILE_BYTES})")
