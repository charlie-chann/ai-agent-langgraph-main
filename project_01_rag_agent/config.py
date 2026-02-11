"""
config.py — 全局配置模块

【职责】
集中管理 RAG 项目的所有可调参数（模型、检索、分块、Agent 行为等）。

【设计原因】
1. 使用 pydantic-settings：启动时自动校验类型，避免配置写错导致运行时崩溃
2. 支持 .env 文件：敏感信息（API Key）和本地差异配置不写死在代码里
3. 保留「Legacy exports」：其他模块可直接 `from config import TOP_K`，
   不必到处写 settings.top_k，降低重构成本
"""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field
import os

# 加载项目根目录下的 .env（若不存在则静默跳过，使用下方默认值）
from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """
    应用配置类 — 所有字段均可通过环境变量或 .env 覆盖。

    Field(alias=...) 表示环境变量名，例如 DEFAULT_MODEL 会映射到 default_model。
    """

    # ── Ollama 本地大模型 ─────────────────────────────────────────────────────
    # base_url：Ollama 服务地址，默认本机 11434 端口
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    # default_model：主 LLM，负责生成回答、评分、改写查询
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    # embedding_model：向量化模型，把文本转成向量存入 ChromaDB（与主模型分离是 RAG 常规做法）
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    # temperature 越低回答越稳定、越「贴文档」；RAG 场景通常用 0.1 左右
    temperature: float = Field(default=0.1, alias="TEMPERATURE")

    # ── 向量库与文档分块 ─────────────────────────────────────────────────────
    # chroma_dir：ChromaDB 持久化目录（嵌入式向量库，无需单独起 DB 服务）
    chroma_dir: Path = Field(default=Path(__file__).parent / "chroma_db")
    collection_name: str = "rag_docs"  # Chroma 集合名，相当于「表名」
    chunk_size: int = 512              # 每个 chunk 最大字符数；太大检索不精准，太小上下文碎片化
    chunk_overlap: int = 64            # 相邻 chunk 重叠字符数，避免句子在边界被截断
    top_k: int = 5                     # 每次检索返回的文档片段数量

    # ── 检索策略 ───────────────────────────────────────────────────────────
    # hybrid = BM25 关键词 + 向量语义；dense = 仅向量；sparse = 仅 BM25
    retrieval_mode: Literal["hybrid", "dense", "sparse"] = Field(default="hybrid", alias="RETRIEVAL_MODE")
    rerank_enabled: bool = Field(default=True, alias="RERANK_ENABLED")  # 是否对候选结果二次精排
    rerank_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="RERANK_MODEL")

    # ── Agent 自校正循环 ───────────────────────────────────────────────────
    max_iterations: int = 2   # 答案评分不通过时，最多重写查询并重检索的次数
    max_tokens: int = 2048    # 生成回答的最大 token（预留，当前由 Ollama 默认控制）

    # ── LangSmith 可观测性（可选）────────────────────────────────────────────
    # 若配置了 Key，会自动开启 LangChain 链路追踪，便于调试 Prompt 和耗时
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")

    class Config:
        env_file = ".env"           # pydantic 也会尝试读 .env
        case_sensitive = False    # 环境变量大小写不敏感


# 全局单例：整个进程共享一份配置
settings = Settings()

# ── 向后兼容的模块级常量 ─────────────────────────────────────────────────────
# 历史代码使用 `from config import TOP_K` 而非 settings.top_k，此处统一导出
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
EMBEDDING_MODEL = settings.embedding_model
TEMPERATURE = settings.temperature
CHROMA_DIR = settings.chroma_dir
COLLECTION_NAME = settings.collection_name
CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
TOP_K = settings.top_k
RETRIEVAL_MODE = settings.retrieval_mode
RERANK_ENABLED = settings.rerank_enabled
RERANK_MODEL = settings.rerank_model
MAX_ITERATIONS = settings.max_iterations
LANGSMITH_ENABLED = settings.langsmith_api_key != ""

# 若用户配置了 LangSmith，注入 LangChain 所需环境变量
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_01_rag_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
