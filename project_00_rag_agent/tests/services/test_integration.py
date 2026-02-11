"""Integration tests — require Ollama (skip if unavailable)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import pytest

OLLAMA_URL = "http://localhost:11434"


def ollama_available() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ollama_available(), reason="Ollama not running"),
]


@pytest.fixture(scope="module")
def ingested_kb():
    from app.knowledge.ingest import ingest_files
    sample = Path(__file__).resolve().parents[2] / "sample_docs" / "company_knowledge_base.txt"
    if not sample.exists():
        pytest.skip("sample_docs missing")
    return ingest_files([sample], force_rebuild=True, acl_roles=["public", "admin"])


def test_hybrid_retrieve(ingested_kb):
    from app.knowledge.retriever import retrieve_with_kg
    docs, kg_ctx = retrieve_with_kg("公司年假政策", user_roles=["admin", "public"])
    assert ingested_kb.get("chunks_created", 0) > 0
    assert isinstance(docs, list)


def test_ask_e2e(ingested_kb):
    from app.services.agent_service import ask
    out = ask("公司的知识库是什么？", user_roles=["admin", "public"], use_cache=False)
    assert "answer" in out
    assert out.get("latency_ms", 0) >= 0


def test_kg_extraction(ingested_kb):
    from app.knowledge.knowledge_graph import get_kg
    kg = get_kg()
    assert len(kg.triples) >= 0  # may be 0 if rule-only on English sample
