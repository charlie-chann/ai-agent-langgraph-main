"""
app/core/config.py — 应用配置（通用 Agent 平台）

【职责】
集中管理 RAG Agent 的全部可调参数：模型 Provider、向量检索、Agent 循环、
超时/熔断、鉴权 RBAC、Redis 缓存与限流、HITL 人机协同、可观测性等。

【设计原因】
1. 使用 pydantic-settings：启动时自动校验类型，避免配置写错导致运行时崩溃
2. 支持按 APP_ENV（local/test/prod）加载 `.env.{env}`，并兼容旧 `.env`
3. 保留「Legacy exports」：其他模块可直接 `from app.core.config import TOP_K`，
   不必到处写 settings.top_k，降低重构成本
4. 按功能域分组（Provider / 检索 / Agent / 超时 / 熔断 …），便于运维按需调整
5. prod 启动护栏：拒绝弱 JWT_SECRET

【与 project_01 差异】
- project_01 仅支持 Ollama 本地模型；本模块新增 OpenAI Provider 双轨切换
- 新增知识图谱（KG）、BM25 稀疏索引路径、Redis 缓存/限流、JWT RBAC、HITL、
  Postgres Checkpointer、熔断器阈值等生产级配置项
- LangSmith 项目名改为 project_00_rag_agent
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from loguru import logger
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# 项目根目录（project_00_rag_agent/）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 支持的部署环境：local=本机开发，test=测试/预发，prod=生产
AppEnv = Literal["local", "test", "prod"]

# 生产环境禁止使用的弱 JWT（含历史示例与 Docker 演示密钥）
_WEAK_JWT_SECRETS = frozenset(
    {
        "change-me-in-production",
        "change-me-in-production-use-long-random-string",
        "docker-dev-secret-change-in-prod",
        "k8s-dev-secret-change-me",
        "test-only-secret-not-for-prod",
    }
)


def _peek_app_env(path: Path) -> str | None:
    """从 dotenv 文件中只窥探 APP_ENV，不完整加载。"""
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, val = s.partition("=")
            if key.strip() == "APP_ENV":
                return val.strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def resolve_app_env() -> AppEnv:
    """从环境变量读取 APP_ENV；非法值回退为 local。"""
    raw = (os.getenv("APP_ENV") or "local").strip().lower()
    if raw in ("local", "test", "prod"):
        return raw  # type: ignore[return-value]
    logger.warning(f"无效 APP_ENV={raw!r}，回退为 local")
    return "local"


def load_env_files(app_env: AppEnv | None = None) -> AppEnv:
    """
    按环境加载配置文件。

    优先级（高 → 低，已存在的进程环境变量不被覆盖）：
      系统/容器注入的环境变量 > `.env.{app_env}` > `.env`

    APP_ENV 发现顺序：
      已导出的 APP_ENV > `.env` 内的 APP_ENV > `.env.local` 内的 APP_ENV > 默认 local
    """
    if not os.getenv("APP_ENV"):
        peeked = _peek_app_env(PROJECT_ROOT / ".env") or _peek_app_env(PROJECT_ROOT / ".env.local")
        if peeked:
            os.environ["APP_ENV"] = peeked

    env = app_env or resolve_app_env()
    os.environ["APP_ENV"] = env

    loaded: list[str] = []
    specific = PROJECT_ROOT / f".env.{env}"
    legacy = PROJECT_ROOT / ".env"
    # 先加载专属文件（优先占坑），再加载 .env 补缺
    if specific.is_file():
        load_dotenv(specific, override=False)
        loaded.append(specific.name)
    if legacy.is_file():
        load_dotenv(legacy, override=False)
        loaded.append(legacy.name)

    if loaded:
        logger.info(f"已加载环境配置: {', '.join(loaded)} (APP_ENV={env})")
    else:
        logger.info(f"未找到 .env.{env} / .env，使用代码默认值 (APP_ENV={env})")
    return env


# 模块导入时即按 APP_ENV 加载对应文件
_ACTIVE_APP_ENV = load_env_files()


class Settings(BaseSettings):
    """
    应用配置类 — 所有字段均可通过环境变量或 .env 覆盖。

    Field(alias=...) 表示环境变量名，例如 LLM_PROVIDER 会映射到 llm_provider。
    """

    # ── 部署环境 ──────────────────────────────────────────────────────────────
    # local | test | prod；决定加载哪份 .env.*，并在 prod 启用启动护栏
    app_env: AppEnv = Field(default="local", alias="APP_ENV")

    # ── Provider ──────────────────────────────────────────────────────────────
    # llm_provider / embedding_provider：支持 ollama（本地）与 openai（云端）双轨
    llm_provider: Literal["ollama", "openai"] = Field(default="ollama", alias="LLM_PROVIDER")
    embedding_provider: Literal["ollama", "openai"] = Field(default="ollama", alias="EMBEDDING_PROVIDER")

    # Ollama 服务地址与 OpenAI 兼容 API 配置
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    # 各 Provider 下的默认模型名；temperature 偏低以保证 RAG 回答稳定、贴文档
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    embedding_model: str = Field(default="nomic-embed-text", alias="EMBEDDING_MODEL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")

    # ── Vector / retrieval ───────────────────────────────────────────────────
    # chroma_dir：ChromaDB 持久化目录；kg_dir：知识图谱三元组存储；bm25_index_path：稀疏索引 pickle
    chroma_dir: Path = Field(default=PROJECT_ROOT / "chroma_db")
    kg_dir: Path = Field(default=PROJECT_ROOT / "kg_store")
    bm25_index_path: Path = Field(default=PROJECT_ROOT / "bm25_index.pkl")
    collection_name: str = "rag_docs_v2"  # v2 与 project_01 的 rag_docs 区分，避免混用
    chunk_size: int = 512                 # 每个 chunk 最大字符数
    chunk_overlap: int = 64               # 相邻 chunk 重叠，避免句子在边界被截断
    top_k: int = 5                        # 每次检索返回的文档片段数量
    # hybrid = BM25 + 向量；dense = 仅向量；sparse = 仅 BM25
    retrieval_mode: Literal["hybrid", "dense", "sparse"] = Field(default="hybrid", alias="RETRIEVAL_MODE")
    rerank_enabled: bool = Field(default=True, alias="RERANK_ENABLED")  # 是否对候选结果二次精排
    rerank_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="RERANK_MODEL")
    kg_enabled: bool = Field(default=True, alias="KG_ENABLED")          # 是否启用知识图谱增强检索
    kg_top_k: int = Field(default=5, alias="KG_TOP_K")                  # KG 检索返回的三元组数量上限

    # ── Agent runtime ─────────────────────────────────────────────────────────
    default_agent_mode: Literal["rag", "react"] = Field(default="rag", alias="DEFAULT_AGENT_MODE")
    cache_namespace: str = Field(default="agent", alias="CACHE_NAMESPACE")

    # ── Agent loop ───────────────────────────────────────────────────────────
    max_iterations: int = 2               # 答案评分不通过时，最多重写查询并重检索的次数
    rag_context_max_tokens: int = 3000    # 注入 Prompt 的 RAG 上下文 token 预算
    history_limit: int = 20               # 对话历史滑动窗口保留的最近消息条数
    summary_enabled: bool = Field(default=True, alias="SUMMARY_ENABLED")  # 是否启用历史摘要（预留）

    # ── Model routing（小模型 aux / 大模型 generate）────────────────────────────
    model_routing_enabled: bool = Field(default=True, alias="MODEL_ROUTING_ENABLED")
    ollama_aux_model: str = Field(default="qwen2.5:1.5b", alias="OLLAMA_AUX_MODEL")
    ollama_generate_model: str = Field(default="", alias="OLLAMA_GENERATE_MODEL")  # 空=default_model
    openai_aux_model: str = Field(default="gpt-4o-mini", alias="OPENAI_AUX_MODEL")
    openai_generate_model: str = Field(default="", alias="OPENAI_GENERATE_MODEL")  # 空=openai_model
    skip_grade_for_simple: bool = Field(default=False, alias="SKIP_GRADE_FOR_SIMPLE")

    # ── Stream / SSE resume ────────────────────────────────────────────────────
    stream_resume_enabled: bool = Field(default=True, alias="STREAM_RESUME_ENABLED")
    stream_wal_ttl_seconds: int = Field(default=3600, alias="STREAM_WAL_TTL_SECONDS")
    stream_flush_chars: int = Field(default=12, alias="STREAM_FLUSH_CHARS")
    stream_flush_interval_ms: int = Field(default=40, alias="STREAM_FLUSH_INTERVAL_MS")
    stream_resume_poll_seconds: float = Field(default=30.0, alias="STREAM_RESUME_POLL_SECONDS")
    stream_cancel_on_disconnect: bool = Field(
        default=False, alias="STREAM_CANCEL_ON_DISCONNECT"
    )  # False=断线后继续写 WAL 供续推

    # ── Timeouts (seconds) ───────────────────────────────────────────────────
    # 各外部调用超时（秒），防止 LLM/Embedding/Rerank 阻塞拖垮整个请求
    llm_timeout: float = 30.0
    embed_timeout: float = 15.0
    rerank_timeout: float = 10.0
    request_timeout: float = 60.0         # 整请求上限，供 API 层或中间件参考

    # ── Circuit breaker ──────────────────────────────────────────────────────
    # 连续失败 cb_failure_threshold 次后熔断；cb_recovery_timeout 秒后进入半开试探
    cb_failure_threshold: int = 5
    cb_recovery_timeout: float = 60.0

    # ── Auth / RBAC ────────────────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    # demo_users_json：演示用用户表，格式 "用户名":"密码:角色"
    # admin:admin123 -> admin, editor:editor123 -> editor, viewer:viewer123 -> viewer
    demo_users_json: str = Field(
        default='{"admin":"admin123:admin","editor":"editor123:editor","viewer":"viewer123:viewer"}',
        alias="DEMO_USERS_JSON",
    )

    # ── Redis cache + rate limit ───────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    cache_ttl_seconds: int = 3600           # 问答结果缓存 TTL（秒）
    rate_limit_requests: int = 60           # 限流窗口内允许的最大请求数
    rate_limit_window_seconds: int = 60     # 限流滑动窗口宽度（秒）

    # ── HITL / Checkpointer ────────────────────────────────────────────────────
    hitl_enabled: bool = Field(default=True, alias="HITL_ENABLED")  # 是否启用人工审批拦截
    # 命中以下关键词时触发 HITL（逗号分隔，大小写由业务层处理）
    hitl_risk_keywords: str = Field(default="delete,drop,truncate,password,secret", alias="HITL_RISK_KEYWORDS")
    # checkpointer_backend：memory 仅进程内；postgres 支持跨进程/重启恢复线程状态
    checkpointer_backend: Literal["memory", "postgres"] = Field(default="memory", alias="CHECKPOINTER_BACKEND")
    database_url: str = Field(
        default="postgresql://rag:rag@localhost:5432/rag_checkpoint",
        alias="DATABASE_URL",
    )
    # conversations_backend：auto=优先 Postgres；sqlite=本地文件；postgres=强制 Postgres
    conversations_backend: Literal["auto", "postgres", "sqlite"] = Field(
        default="auto", alias="CONVERSATIONS_BACKEND"
    )
    conversations_sqlite_path: Path = Field(
        default=PROJECT_ROOT / "data" / "conversations.db",
        alias="CONVERSATIONS_SQLITE_PATH",
    )

    # ── KG extraction ──────────────────────────────────────────────────────────
    # rule=规则抽取；llm=大模型抽取；hybrid=规则优先、LLM 补全
    kg_extraction_mode: Literal["rule", "llm", "hybrid"] = Field(default="hybrid", alias="KG_EXTRACTION_MODE")

    # ── API / UI ───────────────────────────────────────────────────────────────
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_url: str = Field(default="http://localhost:8000", alias="API_BASE_URL")

    # ── Observability ──────────────────────────────────────────────────────────
    # 若配置了 Key，模块末尾会自动开启 LangChain 链路追踪
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}

    @model_validator(mode="after")
    def _enforce_prod_guards(self) -> "Settings":
        """生产环境启动护栏：拒绝弱 JWT，并提示应使用 Postgres。"""
        if self.app_env != "prod":
            return self
        secret = (self.jwt_secret or "").strip()
        if secret in _WEAK_JWT_SECRETS or len(secret) < 32:
            raise ValueError(
                "APP_ENV=prod 时 JWT_SECRET 不能使用默认/弱密钥（长度需 >= 32）。"
                "请在 .env.prod 或部署环境变量中配置强随机密钥。"
            )
        if self.checkpointer_backend == "memory":
            logger.warning(
                "APP_ENV=prod 且 CHECKPOINTER_BACKEND=memory："
                "进程重启后 HITL/checkpoint 会丢失，建议改为 postgres"
            )
        return self


# 全局单例：整个进程共享一份配置
settings = Settings()
# 与 load_env_files 结果对齐（防止 Settings 默认值与实际不一致）
if settings.app_env != _ACTIVE_APP_ENV:
    logger.debug(f"Settings.app_env={settings.app_env}, loader={_ACTIVE_APP_ENV}")

# ── 向后兼容的模块级常量 ─────────────────────────────────────────────────────
# 历史代码使用 `from app.core.config import TOP_K` 而非 settings.top_k，此处统一导出
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
EMBEDDING_MODEL = settings.embedding_model
TEMPERATURE = settings.temperature
CHROMA_DIR = settings.chroma_dir
COLLECTION_NAME = settings.collection_name
CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
TOP_K = settings.top_k
RETRIEVAL_MODE = settings.retrieval_mode
RERANK_ENABLED = settings.rerank_enabled
RERANK_MODEL = settings.rerank_model
MAX_ITERATIONS = settings.max_iterations

# 若用户配置了 LangSmith，注入 LangChain 所需环境变量
if settings.langsmith_api_key:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_00_rag_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
