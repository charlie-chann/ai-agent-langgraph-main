"""
config.py — Project 02 全局配置

【职责】
1. 从 .env 加载 Ollama、搜索、LangSmith 等运行参数
2. 用 Pydantic 做类型校验与默认值兜底
3. 导出模块级常量，供 agent / tools / api 直接 import

【设计原因】
1. 配置与业务逻辑分离：改模型名或端口不用动 agent.py
2. Settings 单例 + 兼容旧变量名（OLLAMA_BASE_URL 等）：避免全项目大改 import
3. LangSmith 可选启用：有 API Key 才打开 tracing，本地开发零依赖
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import os

from dotenv import load_dotenv

# 启动时加载项目根目录下的 .env 文件
load_dotenv()


class Settings(BaseSettings):
    """应用配置类，字段与 .env 中的环境变量一一对应。"""

    # ── Ollama 本地 LLM ─────────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")

    # ── 搜索工具 ────────────────────────────────────────────────────────────
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")

    # ── 代码执行（预留，当前 calculator 用 AST 而非 exec）────────────────────
    code_exec_timeout: int = Field(default=10, alias="CODE_EXEC_TIMEOUT")

    # ── LangSmith 可观测性（可选）──────────────────────────────────────────
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


# 全局配置单例，整个进程共享一份
settings = Settings()


# ── 兼容旧代码的模块级导出 ────────────────────────────────────────────────────
# 其他模块可写 `from config import DEFAULT_MODEL`，不必每次都 settings.xxx
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
TEMPERATURE = settings.temperature
MAX_SEARCH_RESULTS = settings.max_search_results
CODE_EXEC_TIMEOUT = settings.code_exec_timeout
LANGSMITH_ENABLED = settings.langsmith_api_key != ""

# 若配置了 LangSmith Key，自动打开 LangChain tracing
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_02_tool_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
