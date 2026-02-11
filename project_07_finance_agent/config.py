# config.py — project_07_finance_agent
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM ──────────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))

# ── Reports ───────────────────────────────────────────────────────────────────
REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# ── Market Data ───────────────────────────────────────────────────────────────
PRICE_HISTORY_PERIOD: str = os.getenv("PRICE_HISTORY_PERIOD", "1y")
MAX_NEWS_RESULTS: int = int(os.getenv("MAX_NEWS_RESULTS", "5"))

# ── Compliance ────────────────────────────────────────────────────────────────
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.05"))   # 5% annualised
MAX_POSITION_WEIGHT: float = float(os.getenv("MAX_POSITION_WEIGHT", "0.20"))  # 20% cap
VOLATILITY_WARN_THRESHOLD: float = float(os.getenv("VOLATILITY_WARN_THRESHOLD", "0.40"))

# ── LangSmith (optional) ──────────────────────────────────────────────────────
LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_07_finance_agent")
