"""
config.py — project_03_multi_agent 全局配置 (v2.0)

【职责】
1. 从 .env 加载并校验应用级配置（Ollama、Agent 参数、搜索、LangSmith）
2. 提供 Settings 单例与 legacy 常量导出，供 agent / api / app 统一引用
3. 定义业务场景常量（市场调研 / 社媒内容）及 LangSmith 追踪开关

【设计原因】
1. pydantic-settings：类型校验 + 环境变量 alias，避免散落 os.getenv 与类型错误
2. legacy 常量（OLLAMA_BASE_URL 等）：与 project_01/02 保持 import 风格一致，降低迁移成本
3. LangSmith 在模块加载时按需注入环境变量：有 API Key 才开启追踪，无 Key 零开销
4. 场景常量集中定义：agent 路由与 UI 下拉框共用同一套 id，避免字符串硬编码不一致
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import os

from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """
    应用配置模型，支持 .env 与环境变量覆盖默认值。

    所有字段通过 Field alias 映射大写环境变量名（如 OLLAMA_BASE_URL）。
    """

    # ── Ollama LLM 连接参数 ──────────────────────────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    creative_temperature: float = Field(default=0.7, alias="CREATIVE_TEMPERATURE")

    # ── 多 Agent 协作参数 ──────────────────────────────────────────────────────
    max_revision_loops: int = Field(default=2, alias="MAX_REVISION_LOOPS")
    critic_pass_score: int = Field(default=7, alias="CRITIC_PASS_SCORE")
    max_supervisor_turns: int = Field(default=20, alias="MAX_SUPERVISOR_TURNS")
    max_react_iterations: int = Field(default=8, alias="MAX_REACT_ITERATIONS")

    # ── 网络搜索 ──────────────────────────────────────────────────────────────
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")

    # ── LangSmith 可观测性（可选）──────────────────────────────────────────────
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")

    class Config:
        """Pydantic v1 风格配置：指定 env 文件与大小写策略。"""
        env_file = ".env"
        case_sensitive = False


# 全局单例：模块 import 时即完成 .env 加载与校验
settings = Settings()


# ── Legacy 常量导出 ───────────────────────────────────────────────────────────
# 供 `from config import OLLAMA_BASE_URL` 等写法使用，与旧项目保持一致
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
TEMPERATURE = settings.temperature
CREATIVE_TEMPERATURE = settings.creative_temperature
MAX_REVISION_LOOPS = settings.max_revision_loops
CRITIC_PASS_SCORE = settings.critic_pass_score
MAX_SUPERVISOR_TURNS = settings.max_supervisor_turns
MAX_REACT_ITERATIONS = settings.max_react_iterations
MAX_SEARCH_RESULTS = settings.max_search_results
LANGSMITH_ENABLED = settings.langsmith_api_key != ""

# ── 业务场景标识 ──────────────────────────────────────────────────────────────
# agent 根据 scenario 选择不同 Writer Prompt；UI / API 共用同一套 id
SCENARIO_MARKET_RESEARCH = "market_research"
SCENARIO_SOCIAL_MEDIA = "social_media"

# ── LangSmith 追踪初始化 ──────────────────────────────────────────────────────
# 仅在配置了 API Key 时注入环境变量，避免无 Key 时产生无效请求
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_03_multi_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
