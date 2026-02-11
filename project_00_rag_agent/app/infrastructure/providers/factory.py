"""
providers/factory.py — LLM / Embedding 提供者工厂（含模型分流）

【职责】
1. 根据 config 中的 llm_provider / embedding_provider 实例化对应 LangChain 模型
2. model routing：guard/rewrite/grade 走 aux 小模型，generate 走 generate 大模型
3. 与熔断器（circuit_breaker）联动：开路时快速失败

【ModelRole】
  aux      — 非生成任务（guard / rewrite / grade），默认更小更快
  generate — 最终回答生成，可用更大模型
"""
from __future__ import annotations

from typing import Literal, Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from config import settings
from app.core.circuit_breaker import embed_breaker, llm_breaker
from app.core.exceptions import ServiceUnavailableError

ModelRole = Literal["aux", "generate"]


def _resolve_model(role: ModelRole, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if not settings.model_routing_enabled:
        if settings.llm_provider == "openai":
            return settings.openai_model
        return settings.default_model

    if settings.llm_provider == "openai":
        if role == "aux":
            return settings.openai_aux_model or settings.openai_model
        return settings.openai_generate_model or settings.openai_model

    if role == "aux":
        return settings.ollama_aux_model or settings.default_model
    return settings.ollama_generate_model or settings.default_model


def get_chat_model(
    *,
    streaming: bool = False,
    model: Optional[str] = None,
    role: ModelRole = "generate",
) -> BaseChatModel:
    """
    创建并返回聊天模型实例（ChatOpenAI 或 ChatOllama）。

    role=aux 时优先使用配置的轻量模型（guard/rewrite/grade）；
    role=generate 时使用生成专用模型。
    """
    if llm_breaker.is_open():
        raise ServiceUnavailableError("LLM circuit breaker is open")

    resolved = _resolve_model(role, model)
    provider = settings.llm_provider
    try:
        if provider == "openai":
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=resolved,
                api_key=settings.openai_api_key or None,
                base_url=settings.openai_base_url,
                temperature=settings.temperature,
                streaming=streaming,
                timeout=settings.llm_timeout,
            )
        else:
            from langchain_ollama import ChatOllama

            llm = ChatOllama(
                model=resolved,
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
    """创建并返回 Embedding 模型实例。"""
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


def routing_status() -> dict:
    """返回当前模型分流配置（/stats 可观测）。"""
    return {
        "enabled": settings.model_routing_enabled,
        "provider": settings.llm_provider,
        "aux_model": _resolve_model("aux", None),
        "generate_model": _resolve_model("generate", None),
    }
