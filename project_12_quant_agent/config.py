# config.py — Quantitative Research Agent 全局配置
#
# 【职责】管理 LLM 连接、数据源参数、风险计算常量、API 端口。
import os
from dotenv import load_dotenv

load_dotenv()

# ── Ollama LLM（仅用于 generate_research_report 生成文字报告）──────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# ── 数据源参数（yfinance 等，预留）──────────────────────────────────────────
YAHOO_FINANCE_TIMEOUT: int = int(os.getenv("YAHOO_FINANCE_TIMEOUT", "10"))
DEFAULT_PERIOD: str = os.getenv("DEFAULT_PERIOD", "1y")      # K线周期：1d/1mo/1y 等
DEFAULT_INTERVAL: str = os.getenv("DEFAULT_INTERVAL", "1d")  # K线粒度：1d/1h 等

# ── 报告输出 ─────────────────────────────────────────────────────────────────
REPORTS_DIR: str = os.getenv("REPORTS_DIR", "reports")  # AI 研报保存目录

# ── FastAPI 服务 ─────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8012"))

# ── 风险计算参数 ─────────────────────────────────────────────────────────────
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.05"))  # 无风险利率，用于夏普比率
MAX_TICKERS: int = int(os.getenv("MAX_TICKERS", "10"))               # 单次最多分析股票数
