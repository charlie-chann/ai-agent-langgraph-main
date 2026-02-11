"""Unit tests for ask_stream alignment with ask() via astream."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _collect_stream(gen):
    tokens = []
    meta = None
    for token in gen:
        if token.startswith("\n\n__META__"):
            meta = json.loads(token.replace("\n\n__META__", ""))
        else:
            tokens.append(token)
    return "".join(tokens), meta


class TestAskStreamAlignment:
    @patch("agent.cache_get")
    @patch("agent._astream_rag_graph")
    def test_cache_hit_skips_astream(self, mock_astream, mock_cache_get):
        from agent import ask_stream

        mock_cache_get.return_value = {
            "answer": "cached answer",
            "sources": ["a.txt"],
            "grade": "yes",
            "request_id": "rid1",
        }

        answer, meta = _collect_stream(
            ask_stream("q", [], user_roles=["admin"], conversation_id="conv-1")
        )

        assert answer == "cached answer"
        assert meta["cached"] is True
        assert meta["sources"] == ["a.txt"]
        mock_astream.assert_not_called()

    @patch("agent.cache_set")
    @patch("agent.cache_get", return_value=None)
    def test_miss_uses_astream_and_caches(self, _mock_cache_get, mock_cache_set):
        from agent import ask_stream

        async def fake_astream(*_args, sink, **_kwargs):
            sink["state"] = {
                "answer": "fresh answer",
                "sources": ["b.txt"],
                "grade": "yes",
                "latency_ms": 42,
                "request_id": "rid2",
            }
            sink["effective_thread"] = "conv-2"
            yield "fresh answer"

        with patch("agent._astream_rag_graph", side_effect=fake_astream):
            answer, meta = _collect_stream(
                ask_stream(
                    "q",
                    [],
                    user_roles=["admin"],
                    conversation_id="conv-2",
                    use_cache=True,
                )
            )

        assert answer == "fresh answer"
        assert meta["grade"] == "yes"
        assert meta["answer"] == "fresh answer"
        assert meta["cached"] is False
        mock_cache_set.assert_called_once()

    @patch("agent.cache_set")
    @patch("agent.cache_get", return_value=None)
    def test_hitl_pending_does_not_cache(self, _mock_cache_get, mock_cache_set):
        from agent import ask_stream

        async def fake_astream(*_args, sink, **_kwargs):
            sink["state"] = {
                "answer": "Awaiting human approval for high-risk query.",
                "hitl_required": True,
                "hitl_approved": False,
                "sources": [],
                "grade": "unknown",
                "request_id": "rid3",
            }
            sink["effective_thread"] = "conv-3"
            yield "Awaiting human approval for high-risk query."

        with patch("agent._astream_rag_graph", side_effect=fake_astream):
            _answer, meta = _collect_stream(
                ask_stream("delete all data", [], conversation_id="conv-3", use_cache=True)
            )

        assert meta["hitl_pending"] is True
        mock_cache_set.assert_not_called()


@pytest.mark.asyncio
async def test_ask_stream_async_direct():
    from agent import ask_stream_async

    async def fake_astream(*_args, sink, **_kwargs):
        sink["state"] = {"answer": "async", "grade": "yes", "request_id": "r1"}
        sink["effective_thread"] = "t1"
        yield "a"
        yield "sync"

    with patch("agent.cache_get", return_value=None), patch(
        "agent._astream_rag_graph", side_effect=fake_astream
    ):
        tokens = []
        meta = None
        async for token in ask_stream_async("q", []):
            if token.startswith("\n\n__META__"):
                meta = json.loads(token.replace("\n\n__META__", ""))
            else:
                tokens.append(token)

    assert "".join(tokens) == "async"
    assert meta["answer"] == "async"
