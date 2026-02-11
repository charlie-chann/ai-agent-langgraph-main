"""
tools/ingest.py — 文档摄入流水线

【职责】
把用户上传的原始文件（PDF/TXT/MD/DOCX）转化为可检索的向量索引。

【完整流程】
  加载文件 → 切分 chunk → 写入 ChromaDB + 更新 BM25 内存索引

【设计原因】
1. 按文件类型映射 Loader：不同格式用 LangChain 社区最合适的解析器
2. RecursiveCharacterTextSplitter：优先按段落/句号切，中文友好
3. ingest 与 retriever 分离：摄入只负责「写」，检索只负责「读」，职责清晰
"""
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    UnstructuredMarkdownLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from loguru import logger

from config import settings, CHUNK_SIZE, CHUNK_OVERLAP
from tools.retriever import build_vectorstore, get_vectorstore, set_chunks


# 文件扩展名 → Loader 类 的映射表
# 新增格式时只需在此注册，无需改 load_documents 主逻辑
LOADER_MAP = {
    ".pdf": PyPDFLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
    ".markdown": UnstructuredMarkdownLoader,
    ".docx": Docx2txtLoader,
}


def load_documents(
    file_paths: List[str | Path],
    show_progress: bool = True
) -> List[Document]:
    """
    从磁盘加载一个或多个文件，返回 LangChain Document 列表。

    每个 Document 包含：
      - page_content：文本正文
      - metadata：来源文件名、加载时间等（后续用于引用溯源）

    单个文件失败不会中断整批，失败的文件记入 failed 列表。
    """
    docs: List[Document] = []
    failed: List[str] = []

    for i, fp in enumerate(file_paths):
        if show_progress:
            logger.info(f"Loading {i+1}/{len(file_paths)}: {fp}")

        fp = Path(fp)
        suffix = fp.suffix.lower()
        loader_cls = LOADER_MAP.get(suffix)

        if loader_cls is None:
            logger.warning(f"Unsupported file type: {suffix} - {fp.name}")
            failed.append(str(fp))
            continue

        try:
            loader = loader_cls(str(fp))
            loaded = loader.load()

            # 为每个页面/段落补充 metadata，source 用于回答末尾的引用来源
            for doc in loaded:
                doc.metadata.setdefault("source", fp.name)
                doc.metadata["loaded_at"] = datetime.now().isoformat()

            docs.extend(loaded)
            logger.info(f"Loaded {len(loaded)} pages from {fp.name}")

        except Exception as e:
            logger.error(f"Failed to load {fp}: {e}")
            failed.append(str(fp))

    if failed:
        logger.warning(f"Failed to load {len(failed)} files: {failed}")

    return docs


def split_documents(
    docs: List[Document],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[Document]:
    """
    将长文档切分为较小 chunk，便于向量检索精准命中。

    【为什么需要切分】
    LLM 上下文有限，不可能把整本书塞进 Prompt；检索也需要「段落级」粒度。

    【分隔符优先级】
    先按双换行（段落）→ 单换行 → 中文句号等切，尽量保持语义完整。

    add_start_index=True：记录 chunk 在原文中的起始位置，便于溯源。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )

    chunks = splitter.split_documents(docs)

    # 附加 chunk 序号，调试时可知道「第几段」被检索到
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = len(chunks)

    logger.info(f"Split into {len(chunks)} chunks")
    return chunks


def ingest_files(
    file_paths: List[str | Path],
    force_rebuild: bool = False,
    show_progress: bool = True,
) -> dict:
    """
    完整摄入流水线：load → split → build_vectorstore。

    Args:
        file_paths: 待摄入文件路径列表
        force_rebuild: True 时删除旧 Chroma 集合并重建（换文档时常用）

    Returns:
        统计 dict：files_loaded, chunks_created, documents_indexed, error_count
    """
    # 步骤 1：加载原始文档
    docs = load_documents(file_paths, show_progress)

    if not docs:
        logger.error("No documents loaded")
        return {
            "files_loaded": 0,
            "chunks_created": 0,
            "error_count": 0,
        }

    # 步骤 2：切分为 chunk
    chunks = split_documents(docs)

    if not chunks:
        logger.error("No chunks created")
        return {
            "files_loaded": len(docs),
            "chunks_created": 0,
            "error_count": 0,
        }

    # 步骤 3：写入向量库（同时更新 BM25 内存索引，见 retriever.build_vectorstore）
    try:
        vs = build_vectorstore(chunks, force_rebuild=force_rebuild)
        doc_count = vs._collection.count()
        logger.info(f"Ingestion complete: {len(chunks)} chunks indexed")
    except Exception as e:
        logger.error(f"Vectorstore build failed: {e}")
        return {
            "files_loaded": len(docs),
            "chunks_created": len(chunks),
            "error_count": 1,
        }

    return {
        "files_loaded": len(docs),
        "chunks_created": len(chunks),
        "documents_indexed": doc_count,
        "error_count": 0,
    }


def ingest_folder(
    folder_path: str | Path,
    extensions: Optional[List[str]] = None,
    force_rebuild: bool = False,
) -> dict:
    """
    递归扫描文件夹，摄入所有支持格式的文件。

    典型用法：ingest_folder('./sample_docs')
    rglob 会搜索子目录，适合批量导入知识库目录。
    """
    folder = Path(folder_path)

    if extensions is None:
        extensions = [".pdf", ".txt", ".md", ".markdown", ".docx"]

    files = []
    for ext in extensions:
        files.extend(folder.rglob(f"*{ext}"))

    logger.info(f"Found {len(files)} files in {folder}")

    return ingest_files(files, force_rebuild=force_rebuild)


def get_document_stats() -> dict:
    """
    查询当前向量库状态：共多少 chunk、来自哪些源文件。

    可用于管理后台或调试「文档是否已成功摄入」。
    """
    try:
        vs = get_vectorstore()
        doc_count = vs._collection.count()

        results = vs.get()
        sources = set()
        for meta in results.get("metadatas", []):
            if meta and "source" in meta:
                sources.add(meta["source"])

        return {
            "total_chunks": doc_count,
            "unique_sources": len(sources),
            "sources": list(sources),
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {
            "total_chunks": 0,
            "unique_sources": 0,
            "sources": [],
            "error": str(e),
        }
