# tests/test_agent.py
import sys
from pathlib import Path

# Ensure project root is on sys.path before project modules are imported
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from langchain_core.documents import Document


@pytest.fixture
def sample_docs():
    return [
        Document(page_content="LangChain is a framework for LLM applications.", metadata={"source": "test.txt"}),
        Document(page_content="Ollama runs large language models locally.", metadata={"source": "test.txt"}),
        Document(page_content="RAG combines retrieval with generation.", metadata={"source": "test.txt"}),
    ]


def test_split_documents(sample_docs):
    from tools.ingest import split_documents
    chunks = split_documents(sample_docs)
    assert len(chunks) >= len(sample_docs)
    for c in chunks:
        assert len(c.page_content) <= 600  # chunk_size + some tolerance


def test_rerank_docs(sample_docs):
    from tools.retriever import rerank_docs
    result = rerank_docs(sample_docs, "What is LangChain?", top_n=2)
    assert len(result) == 2
    # The LangChain doc should rank first
    assert "LangChain" in result[0].page_content


def test_rag_node_rewrite():
    """Test rewrite node in isolation — imports scoped to avoid global 'agent' pkg conflict."""
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "project01_agent",
        Path(__file__).parent.parent / "agent.py",
    )
    mod = importlib.util.module_from_spec(spec)
    # Minimal state — rewrite on first iter just passes through
    state = {
        "question": "What is RAG?",
        "iterations": 0,
        "chat_history": [],
        "context_docs": [],
        "sources": [],
        "answer": "",
        "grade": "",
        "latency_ms": 0,
        "rewritten_question": "",
    }
    spec.loader.exec_module(mod)
    result = mod.node_rewrite(state)
    assert result["rewritten_question"] == "What is RAG?"
