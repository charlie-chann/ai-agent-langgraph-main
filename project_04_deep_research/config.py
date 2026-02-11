"""
config.py — project_04_deep_research 全局配置模块

【职责】
集中管理 Deep Research Agent 的运行参数：LLM 连接、研究循环控制、
报告输出路径，以及 LangSmith 可观测性开关。

【设计原因】
将配置与业务逻辑分离，便于通过 .env 或环境变量在不同部署环境
（本地开发 / Docker / 生产）间切换，无需修改代码。
"""
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件，使本地开发时 API Key 等敏感信息不入库
load_dotenv()

# ── LLM 连接参数 ──────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
CREATIVE_TEMPERATURE: float = float(os.getenv("CREATIVE_TEMPERATURE", "0.6"))

# ── 研究循环控制参数 ──────────────────────────────────────────────────────────
MAX_SEARCH_ROUNDS: int = int(os.getenv("MAX_SEARCH_ROUNDS", "4"))
SEARCHES_PER_ROUND: int = int(os.getenv("SEARCHES_PER_ROUND", "3"))
SUFFICIENCY_THRESHOLD: float = float(os.getenv("SUFFICIENCY_THRESHOLD", "0.8"))  # 0-1

# ── 报告输出 ─────────────────────────────────────────────────────────────────
REPORT_OUTPUT_DIR: str = os.getenv("REPORT_OUTPUT_DIR", "./reports")

# ── LangSmith 链路追踪 ────────────────────────────────────────────────────────
# 仅当配置了 LANGSMITH_API_KEY 时才启用，避免无 Key 时产生无效请求
LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_04_deep_research")
