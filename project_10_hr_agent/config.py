# config.py — HR/Recruitment Screening Agent configuration
import os
from dotenv import load_dotenv

load_dotenv()

# ── Ollama ──────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
CREATIVE_TEMPERATURE: float = float(os.getenv("CREATIVE_TEMPERATURE", "0.5"))

# ── HR Agent Settings ────────────────────────────────────────────────────────
MAX_CANDIDATES_PER_BATCH: int = int(os.getenv("MAX_CANDIDATES_PER_BATCH", "50"))
RESUME_MAX_CHARS: int = int(os.getenv("RESUME_MAX_CHARS", "5000"))
SCORE_THRESHOLD_SHORTLIST: float = float(os.getenv("SCORE_THRESHOLD_SHORTLIST", "0.65"))
SCORE_THRESHOLD_REJECT: float = float(os.getenv("SCORE_THRESHOLD_REJECT", "0.35"))

# ── Storage ──────────────────────────────────────────────────────────────────
CANDIDATES_DB_PATH: str = os.getenv("CANDIDATES_DB_PATH", "candidates_db.json")
REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")

# ── API ─────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8010"))

# ── LangSmith (optional) ─────────────────────────────────────────────────────
LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "hr-agent")
