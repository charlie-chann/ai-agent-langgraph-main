"""
Self-Evolving RAG System Configuration
自进化RAG系统配置
"""
import os
from pathlib import Path

# ============ 核心路径 ============
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
FEEDBACK_DB = DATA_DIR / "feedback.db"
EVOLUTION_LOG = DATA_DIR / "evolution_log.json"
CONFIG_FILE = DATA_DIR / "config.json"

# ============ Ollama 配置 ============
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text:latest"  # 嵌入模型（专用于向量检索）
OLLAMA_LLM_MODEL = "qwen2.5:1.5b"              # 主模型（问答生成）
OLLAMA_TIMEOUT = 120

# ============ 向量库配置 ============
VECTOR_DB_TYPE = "chroma"  # chroma | faiss
CHROMA_COLLECTION_NAME = "self_evolving_rag"
EMBEDDING_DIM = 768  # nomic-embed-text 输出维度

# ============ 文档处理配置 ============
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
MAX_DOC_SIZE_MB = 50

# ============ RAG 检索配置 ============
DEFAULT_TOP_K = 5
MAX_CONTEXT_CHUNKS = 8
SIMILARITY_THRESHOLD = 0.3

# ============ 自进化配置 ============
EVOLUTION_TRIGGER_THRESHOLD = 5   # 收到N条反馈后触发自进化
POSITIVE_THRESHOLD = 0.7          # 好评阈值
NEGATIVE_THRESHOLD = 0.3           # 差评阈值
BOOST_WEIGHT = 0.1                # 每次进化对权重的调整幅度
AUTO_RETRAIN_INTERVAL = 10        # 自动触发进化的反馈数

# ============ UI 配置 ============
STREAMLIT_THEME = "dark"
PAGE_ICON = "🧠"
LAYOUT = "wide"

# ============ 支持的文件类型 ============
SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".doc",
    ".html", ".htm", ".json", ".yaml", ".yml",
    ".csv", ".tsv", ".py", ".js", ".cpp", ".java"
}

# ============ 初始化目录 ============
for d in [DATA_DIR, VECTOR_STORE_DIR]:
    d.mkdir(parents=True, exist_ok=True)
