"""
文档处理器
支持多格式加载、文本清洗、智能分块
"""
import re
import uuid
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from langchain_community.document_loaders import (
    TextLoader, CSVLoader, PDFMinerLoader,
    Docx2txtLoader, UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from config import (
    CHUNK_SIZE, CHUNK_OVERLAP, SUPPORTED_EXTENSIONS,
    MAX_DOC_SIZE_MB
)


class DocumentProcessor:
    """文档处理器：加载 → 分块 → 元数据生成"""

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", "。", "！", "？", " ", ""],
            length_function=len,
        )

    def load_file(self, file_path: str) -> List[Document]:
        """
        根据文件类型选择加载器
        返回文档列表
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"不支持的文件类型: {suffix}")

        # 检查文件大小
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_DOC_SIZE_MB:
            raise ValueError(f"文件过大 ({size_mb:.1f}MB)，请控制在{MAX_DOC_SIZE_MB}MB以内")

        try:
            if suffix == ".txt" or suffix == ".md":
                loader = TextLoader(file_path, encoding="utf-8")
            elif suffix == ".csv":
                loader = CSVLoader(file_path, encoding="utf-8")
            elif suffix == ".pdf":
                loader = PDFMinerLoader(file_path)
            elif suffix in [".docx", ".doc"]:
                loader = Docx2txtLoader(file_path)
            elif suffix in [".html", ".htm"]:
                loader = UnstructuredHTMLLoader(file_path)
            elif suffix in [".json", ".yaml", ".yml"]:
                # 自定义JSON/YAML处理
                return self._load_structured(file_path, suffix)
            else:
                loader = TextLoader(file_path, encoding="utf-8")

            docs = loader.load()
            return docs

        except Exception as e:
            raise RuntimeError(f"加载文件失败: {e}")

    def _load_structured(self, file_path: str, suffix: str) -> List[Document]:
        """处理JSON/YAML等结构化文件"""
        import json as json_lib

        docs = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if suffix == ".json":
                    data = json_lib.load(f)
                else:
                    import yaml
                    data = yaml.safe_load(f)

            # 将结构化数据转为文本
            text = json_lib.dumps(data, ensure_ascii=False, indent=2)
            docs.append(Document(
                page_content=text[:10000],  # 截断过长的JSON
                metadata={"source": file_path, "type": suffix}
            ))
        except Exception as e:
            raise RuntimeError(f"加载结构化文件失败: {e}")

        return docs

    def process_file(self, file_path: str) -> Tuple[List[str], List[dict]]:
        """
        完整处理流程：加载 → 分块 → 生成元数据
        返回: (chunks, metadatas)
        """
        docs = self.load_file(file_path)
        path = Path(file_path)

        # 合并所有文档内容（按需可保持分文档结构）
        full_text = "\n\n".join([doc.page_content for doc in docs])

        # 清洗文本
        cleaned_text = self._clean_text(full_text)

        # 分块
        chunks = self.text_splitter.split_text(cleaned_text)

        # 生成元数据
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source": path.name,
                "source_path": str(path.absolute()),
                "chunk_index": i,
                "total_chunks": len(chunks),
                "boost_score": 0.0,           # 进化权重
                "hit_count": 0,               # 被检索命中次数
                "last_accessed": None,
                "created_at": datetime.now().isoformat(),
                "file_type": path.suffix,
                "doc_id": self._generate_doc_id(path, i),
            }
            metadatas.append(metadata)

        return chunks, metadatas

    def process_folder(self, folder_path: str, recursive: bool = True) -> Tuple[List[str], List[dict]]:
        """
        批量处理文件夹
        """
        path = Path(folder_path)
        all_chunks = []
        all_metas = []

        pattern = "**/*" if recursive else "*"
        for file_path in path.glob(pattern):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    chunks, metas = self.process_file(str(file_path))
                    all_chunks.extend(chunks)
                    all_metas.extend(metas)
                except Exception as e:
                    print(f"[DocumentProcessor] 处理失败 {file_path}: {e}")
                    continue

        return all_chunks, all_metas

    def _clean_text(self, text: str) -> str:
        """清洗文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊控制字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # 移除URL（可选）
        # text = re.sub(r'http[s]?://\S+', '[链接]', text)
        return text.strip()

    def _generate_doc_id(self, path: Path, chunk_index: int) -> str:
        """生成文档chunk的唯一ID"""
        content = f"{path.name}_{chunk_index}_{path.stat().st_mtime}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """纯文本分块工具"""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_text(text)
