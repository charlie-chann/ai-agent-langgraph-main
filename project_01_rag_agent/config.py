# config.py — project_01_rag_agent (v2.0)
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()


# ── Settings ─────────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    
    # Vector Store
    chroma_dir: Path = Field(default=Path(__file__).parent / "chroma_db")
    collection_name: str = "rag_docs"
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5
    
    # Retrieval
    retrieval_mode: Literal["hybrid", "dense", "sparse"] = Field(default="hybrid", alias="RETRIEVAL_MODE")
    rerank_enabled: bool = Field(default=True, alias="RERANK_ENABLED")
    rerank_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="RERANK_MODEL")
    
    # Agent
    max_iterations: int = 2
    max_tokens: int = 2048
    
    # LangSmith
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# ── Legacy exports for backward compatibility ─────────────────────────────────
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

# LangSmith setup
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_01_rag_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
