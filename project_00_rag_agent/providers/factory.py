"""
factory.py — LLM / Embedding 提供者工厂

【职责】
1. 根据 config 中的 llm_provider / embedding_provider 实例化对应 LangChain 模型
2. 统一封装 Ollama 与 OpenAI 兼容后端的创建逻辑
3. 与熔断器（circuit_breaker）联动：开路时快速失败，成功/失败时更新计数

【设计原因】
1. 工厂模式集中切换后端，业务代码只调用 get_chat_model / get_embeddings
2. 延迟 import（函数内 import）避免未使用的 provider 包在启动时强依赖
3. 熔断器防止下游 LLM/Embedding 持续故障时拖垮整个 API
4. streaming 参数由调用方传入，同一工厂可服务流式与非流式场景

【支持的 Provider】
  llm_provider       — "ollama" | "openai"
  embedding_provider — "ollama" | "openai"
"""
from __future__ import annotations

from typing import Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from config import settings
from core.circuit_breaker import embed_breaker, llm_breaker
from core.exceptions import ServiceUnavailableError


def get_chat_model(*, streaming: bool = False, model: Optional[str] = None) -> BaseChatModel:
    """
    创建并返回聊天模型实例（ChatOpenAI 或 ChatOllama）。

    - 熔断器开路 → ServiceUnavailableError
    - model 未指定时使用 settings 中对应 provider 的默认模型
    - 创建成功/失败分别调用 llm_breaker.record_success / record_failure
    """
    if llm_breaker.is_open():
        raise ServiceUnavailableError("LLM circuit breaker is open")

    provider = settings.llm_provider
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=model or settings.openai_model,
                api_key=settings.openai_api_key or None,
                base_url=settings.openai_base_url,
                temperature=settings.temperature,
                streaming=streaming,
                timeout=settings.llm_timeout,
            )
        else:
            from langchain_ollama import ChatOllama

            llm = ChatOllama(
                model=model or settings.default_model,
                base_url=settings.ollama_base_url,
                temperature=settings.temperature,
                streaming=streaming,
            )
        llm_breaker.record_success()
        return llm
    except Exception:
        llm_breaker.record_failure()
        raise


def get_embeddings() -> Embeddings:
    """
    创建并返回 Embedding 模型实例（OpenAIEmbeddings 或 OllamaEmbeddings）。

    逻辑与 get_chat_model 对称：熔断检查 → 按 provider 分支 → 更新 embed_breaker。
    """
    if embed_breaker.is_open():
        raise ServiceUnavailableError("Embedding circuit breaker is open")

    provider = settings.embedding_provider
    try:
        if provider == "openai":
            from langchain_openai import OpenAIEmbeddings

            emb = OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key or None,
                base_url=settings.openai_base_url,
                timeout=settings.embed_timeout,
            )
        else:
            from langchain_ollama import OllamaEmbeddings

            emb = OllamaEmbeddings(
                model=settings.embedding_model,
                base_url=settings.ollama_base_url,
            )
        embed_breaker.record_success()
        return emb
    except Exception:
        embed_breaker.record_failure()
        raise
