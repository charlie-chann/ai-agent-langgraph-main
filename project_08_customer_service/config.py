# config.py — project_08_customer_service 客服全链路 Agent 配置
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM 配置 ──────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "8"))

# ── 客服业务配置 ───────────────────────────────────────────────────────────────
COMPANY_NAME: str = os.getenv("COMPANY_NAME", "智慧科技有限公司")
SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "support@company.com")

# ── 升级规则 ──────────────────────────────────────────────────────────────────
# 负面情绪分数超过此阈值时自动升级
ESCALATION_SENTIMENT_THRESHOLD: float = float(os.getenv("ESCALATION_SENTIMENT_THRESHOLD", "0.7"))
# 同一用户连续未解决工单数超此值触发升级
ESCALATION_TICKET_THRESHOLD: int = int(os.getenv("ESCALATION_TICKET_THRESHOLD", "3"))

# ── 工单配置 ──────────────────────────────────────────────────────────────────
# 工单SLA（小时）：P1=紧急, P2=高, P3=正常, P4=低
SLA_HOURS: dict = {
    "P1": int(os.getenv("SLA_P1_HOURS", "2")),
    "P2": int(os.getenv("SLA_P2_HOURS", "8")),
    "P3": int(os.getenv("SLA_P3_HOURS", "24")),
    "P4": int(os.getenv("SLA_P4_HOURS", "72")),
}

# ── 知识库 ────────────────────────────────────────────────────────────────────
KB_DIR: str = os.getenv("KB_DIR", "knowledge_base")
MAX_KB_RESULTS: int = int(os.getenv("MAX_KB_RESULTS", "3"))

# ── LangSmith（可选） ─────────────────────────────────────────────────────────
LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_08_customer_service")
