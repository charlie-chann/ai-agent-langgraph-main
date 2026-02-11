"""
tests/test_agent.py — 单元测试

【测试范围】
不依赖 Ollama 在线的部分（切分、重排、rewrite 节点逻辑）。
完整端到端问答测试需要本地 Ollama + 已 ingest 的向量库，放在集成测试或手动验证。
"""
import sys
from pathlib import Path

# 把 project_01_rag_agent 根目录加入 sys.path，使 `from tools.xxx` 可导入
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from langchain_core.documents import Document


@pytest.fixture
def sample_docs():
    """构造三条英文样例 Document，供切分/重排测试使用。"""
    return [
        Document(page_content="LangChain is a framework for LLM applications.", metadata={"source": "test.txt"}),
        Document(page_content="Ollama runs large language models locally.", metadata={"source": "test.txt"}),
        Document(page_content="RAG combines retrieval with generation.", metadata={"source": "test.txt"}),
    ]


def test_split_documents(sample_docs):
    """验证 split_documents 不会把 chunk 切得过大（<= chunk_size + 容差）。"""
    from tools.ingest import split_documents
    chunks = split_documents(sample_docs)
    assert len(chunks) >= len(sample_docs)
    for c in chunks:
        assert len(c.page_content) <= 600  # chunk_size(512) + 容差


def test_rerank_docs(sample_docs):
    """验证 rerank：问 LangChain 时，含 LangChain 的文档应排到第一。"""
    from tools.retriever import rerank_docs
    result = rerank_docs(sample_docs, "What is LangChain?", top_n=2)
    assert len(result) == 2
    assert "LangChain" in result[0].page_content


def test_rag_node_rewrite():
    """
    隔离测试 node_rewrite：第一次迭代（iterations=0）应原样返回问题，不调用 LLM。

    使用 importlib 动态加载 agent.py，避免与全局包名 agent 冲突。
    """
    import importlib
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "project01_agent",
        Path(__file__).parent.parent / "agent.py",
    )
    mod = importlib.util.module_from_spec(spec)
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
