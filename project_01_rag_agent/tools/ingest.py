# tools/ingest.py — document ingestion pipeline v2.0
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
    """Load documents from file paths."""
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
            
            # Add metadata
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
    """Split documents into chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    
    chunks = splitter.split_documents(docs)
    
    # Add chunk metadata
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
    Full ingestion pipeline: load → split → build vectorstore.
    
    Returns:
        dict with stats: files_loaded, chunks_created, error_count
    """
    # 1. Load documents
    docs = load_documents(file_paths, show_progress)
    
    if not docs:
        logger.error("No documents loaded")
        return {
            "files_loaded": 0,
            "chunks_created": 0,
            "error_count": 0,
        }
    
    # 2. Split into chunks
    chunks = split_documents(docs)
    
    if not chunks:
        logger.error("No chunks created")
        return {
            "files_loaded": len(docs),
            "chunks_created": 0,
            "error_count": 0,
        }
    
    # 3. Build vectorstore
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
    Ingest all supported files in a folder.
    
    Args:
        folder_path: Path to folder
        extensions: File extensions to include (default: .pdf, .txt, .md, .docx)
        force_rebuild: Whether to rebuild vectorstore from scratch
    """
    folder = Path(folder_path)
    
    if extensions is None:
        extensions = [".pdf", ".txt", ".md", ".markdown", ".docx"]
    
    # Find all matching files
    files = []
    for ext in extensions:
        files.extend(folder.rglob(f"*{ext}"))
    
    logger.info(f"Found {len(files)} files in {folder}")
    
    return ingest_files(files, force_rebuild=force_rebuild)


def get_document_stats() -> dict:
    """Get current document stats."""
    try:
        vs = get_vectorstore()
        doc_count = vs._collection.count()
        
        # Get unique sources
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
