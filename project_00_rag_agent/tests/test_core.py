"""Basic unit tests for project_00_rag_agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util
import pytest


def _load(name, rel):
    path = Path(__file__).parent.parent / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class TestCompression:
    def setup_method(self):
        self.mod = _load("compression", "core/compression.py")

    def test_trim_context_budget(self):
        chunks = ["a" * 100, "b" * 100, "c" * 10000]
        out = self.mod.trim_context_chunks(chunks, max_tokens=50)
        assert len(out) < len("".join(chunks))

    def test_dict_history(self):
        msgs = self.mod.dict_history_to_messages([
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        assert len(msgs) == 2


class TestAuth:
    def setup_method(self):
        self.mod = _load("middleware.auth", "middleware/auth.py")

    def test_authenticate_admin(self):
        user = self.mod.authenticate_user("admin", "admin123")
        assert user is not None
        assert user.role == "admin"

    def test_authenticate_fail(self):
        assert self.mod.authenticate_user("admin", "wrong") is None

    def test_token_roundtrip(self):
        user = self.mod.TokenPayload(sub="admin", role="admin")
        token = self.mod.create_access_token(user)
        decoded = self.mod.decode_token(token)
        assert decoded.sub == "admin"


class TestKnowledgeGraph:
    def setup_method(self):
        self.mod = _load("tools.knowledge_graph", "tools/knowledge_graph.py")

    def test_extract_triples(self):
        from langchain_core.documents import Document
        doc = Document(
            page_content="《年假管理办法 v3》规定 高管年假 15天",
            metadata={"source": "policy.txt"},
        )
        triples = self.mod.extract_triples_from_chunk(doc)
        assert len(triples) >= 1

    def test_kg_query(self):
        kg = self.mod.KnowledgeGraph()
        kg.add_triple(self.mod.Triple("年假", "defines", "15天", "policy.txt"))
        results = kg.query("年假多少天")
        assert len(results) >= 1


class TestIngestValidation:
    def setup_method(self):
        self.mod = _load("ingest", "tools/ingest.py")

    def test_sanitize_filename(self):
        assert ".." not in self.mod.sanitize_filename("../../etc/passwd")

    def test_validate_unsupported(self):
        from core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            self.mod.validate_upload("malware.exe", 100)


class TestFileToolPatterns:
    """Path traversal pattern from project_06 style."""

    def test_safe_path_logic(self):
        from pathlib import Path
        sandbox = Path("/tmp/test_sandbox").resolve()
        p = (sandbox / "../../etc/passwd").resolve()
        assert not str(p).startswith(str(sandbox))
