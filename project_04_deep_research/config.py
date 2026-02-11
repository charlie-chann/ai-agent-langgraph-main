# config.py — project_04_deep_research
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
CREATIVE_TEMPERATURE: float = float(os.getenv("CREATIVE_TEMPERATURE", "0.6"))

# Research loop settings
MAX_SEARCH_ROUNDS: int = int(os.getenv("MAX_SEARCH_ROUNDS", "4"))
SEARCHES_PER_ROUND: int = int(os.getenv("SEARCHES_PER_ROUND", "3"))
SUFFICIENCY_THRESHOLD: float = float(os.getenv("SUFFICIENCY_THRESHOLD", "0.8"))  # 0-1

# Output
REPORT_OUTPUT_DIR: str = os.getenv("REPORT_OUTPUT_DIR", "./reports")

LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_04_deep_research")
