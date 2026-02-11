# config.py — Quantitative Research Agent 配置
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# 数据源
YAHOO_FINANCE_TIMEOUT: int = int(os.getenv("YAHOO_FINANCE_TIMEOUT", "10"))
DEFAULT_PERIOD: str = os.getenv("DEFAULT_PERIOD", "1y")      # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y
DEFAULT_INTERVAL: str = os.getenv("DEFAULT_INTERVAL", "1d")  # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d

# 报告输出
REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")

# API
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8012"))

# 风险参数
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.05"))  # 无风险利率（美债）
MAX_TICKERS: int = int(os.getenv("MAX_TICKERS", "10"))               # 单次最多分析股票数
