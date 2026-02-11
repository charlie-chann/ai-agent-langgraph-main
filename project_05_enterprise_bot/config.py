# config.py — project_05_enterprise_bot
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# Memory
MAX_HISTORY_MESSAGES: int = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

# RBAC roles
ROLES = {
    "admin":    {"level": 3, "can": ["create_ticket", "close_ticket", "list_all_tickets", "send_notification", "search_kb", "create_user", "view_reports"]},
    "manager":  {"level": 2, "can": ["create_ticket", "close_ticket", "list_all_tickets", "send_notification", "search_kb", "view_reports"]},
    "employee": {"level": 1, "can": ["create_ticket", "search_kb", "list_my_tickets"]},
    "guest":    {"level": 0, "can": ["search_kb"]},
}

LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_05_enterprise_bot")
