"""健康检查与就绪探针用例。"""
from __future__ import annotations

from app.core.circuit_breaker import embed_breaker, llm_breaker
from app.infrastructure.persistence.conversations import get_conversation_store
from app.knowledge.retriever import get_vectorstore


def get_readiness() -> tuple[int, dict]:
    """返回 (HTTP 状态码, 就绪检查体)。"""
    checks = {
        "chroma": False,
        "llm_circuit": not llm_breaker.is_open(),
        "embed_circuit": not embed_breaker.is_open(),
        "conversations": False,
    }
    try:
        get_vectorstore()
        checks["chroma"] = True
    except Exception as e:
        checks["chroma_error"] = str(e)
    try:
        store = get_conversation_store()
        checks["conversations"] = True
        checks["conversations_backend"] = store.backend_name()
    except Exception as e:
        checks["conversations_error"] = str(e)

    status = (
        "ready"
        if all(
            v
            for k, v in checks.items()
            if not k.endswith("_error") and k != "conversations_backend"
        )
        else "degraded"
    )
    code = 200 if status == "ready" else 503
    return code, {"status": status, "checks": checks}
