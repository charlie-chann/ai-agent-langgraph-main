"""
config.py — project_05_enterprise_bot 全局配置模块

【职责】
集中管理企业机器人项目的运行参数：LLM 连接、对话记忆上限、RBAC 角色权限表，
以及 LangSmith 可观测性开关。所有模块通过 import 本文件获取统一配置。

【设计原因】
将环境变量与业务常量从业务代码中剥离，便于部署时通过 .env 切换模型/端点，
且 RBAC 权限表集中定义，避免各工具模块重复维护角色-动作映射。
"""
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件，使后续 os.getenv 能读取本地密钥与覆盖项
load_dotenv()

# ── LLM 连接参数 ──────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# ── 对话记忆 ──────────────────────────────────────────────────────────────────
# 每个用户保留的最大历史消息条数（Human + AI 各算一条）
MAX_HISTORY_MESSAGES: int = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

# ── RBAC 角色权限表 ───────────────────────────────────────────────────────────
# level 数值越高权限越大；can 列表中的字符串与 LangChain 工具 name 一一对应
ROLES = {
    "admin":    {"level": 3, "can": ["create_ticket", "close_ticket", "list_all_tickets", "send_notification", "search_kb", "create_user", "view_reports"]},
    "manager":  {"level": 2, "can": ["create_ticket", "close_ticket", "list_all_tickets", "send_notification", "search_kb", "view_reports"]},
    "employee": {"level": 1, "can": ["create_ticket", "search_kb", "list_my_tickets"]},
    "guest":    {"level": 0, "can": ["search_kb"]},
}

# ── LangSmith 链路追踪 ────────────────────────────────────────────────────────
# 仅当配置了 LANGSMITH_API_KEY 时才启用，避免本地开发产生无效追踪请求
LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_05_enterprise_bot")
