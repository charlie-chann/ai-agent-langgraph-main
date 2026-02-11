# config.py — Legal Contract Review Agent 配置
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# 合同分析配置
MAX_CONTRACT_CHARS: int = int(os.getenv("MAX_CONTRACT_CHARS", "20000"))
RISK_THRESHOLD_HIGH: float = float(os.getenv("RISK_THRESHOLD_HIGH", "0.7"))
RISK_THRESHOLD_MEDIUM: float = float(os.getenv("RISK_THRESHOLD_MEDIUM", "0.4"))

# 报告输出
REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")

# API
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8011"))
