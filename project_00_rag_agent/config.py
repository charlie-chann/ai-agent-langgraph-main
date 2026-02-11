"""根目录兼容入口：转发到 app.core.config。"""
from app.core.config import *  # noqa: F401,F403
from app.core.config import (  # noqa: F401
    PROJECT_ROOT,
    settings,
    OLLAMA_BASE_URL,
    DEFAULT_MODEL,
    EMBEDDING_MODEL,
    TEMPERATURE,
    CHROMA_DIR,
    COLLECTION_NAME,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TOP_K,
    RETRIEVAL_MODE,
    RERANK_ENABLED,
    RERANK_MODEL,
    MAX_ITERATIONS,
)
