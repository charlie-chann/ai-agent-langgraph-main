"""Tests for stream WAL, SSE batching, and model routing."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestStreamWAL:
    def test_append_and_read_events(self):
        from app.infrastructure.persistence import stream_wal

        with patch.object(stream_wal.settings, "stream_resume_enabled", True):
            stream_wal._mem_streams.clear()
            stream_wal._redis_client = False
            stream_wal.begin_stream("s1", conversation_id="c1", request_id="s1", message="hi")
            o1 = stream_wal.append_event("s1", "token", {"token": "hello"})
            o2 = stream_wal.append_event("s1", "token", {"token": " world"})
            stream_wal.finalize_stream("s1", status="complete")

            events = stream_wal.read_events("s1", after_offset=0)
            assert [e.offset for e in events] == [o1, o2]
            assert events[0].payload["token"] == "hello"
            assert stream_wal.get_stream_status("s1")["status"] == "complete"


class TestStreamingBatch:
    @pytest.mark.asyncio
    async def test_batched_tokens_flush_by_chars(self):
        from app.core.streaming import batched_tokens

        async def _src():
            for t in ["a", "b", "c", "d"]:
                yield t

        out = []
        async for batch in batched_tokens(_src(), flush_chars=2, flush_interval_ms=9999):
            out.append(batch)
        assert out == ["ab", "cd"]


class TestModelRouting:
    def test_resolve_aux_and_generate(self):
        from app.infrastructure.providers.factory import _resolve_model

        with patch("app.infrastructure.providers.factory.settings") as mock_settings:
            mock_settings.model_routing_enabled = True
            mock_settings.llm_provider = "ollama"
            mock_settings.default_model = "default"
            mock_settings.ollama_aux_model = "small"
            mock_settings.ollama_generate_model = "large"
            mock_settings.openai_model = "gpt-4o-mini"
            mock_settings.openai_aux_model = "gpt-4o-mini"
            mock_settings.openai_generate_model = ""

            assert _resolve_model("aux", None) == "small"
            assert _resolve_model("generate", None) == "large"

    @patch("app.agent.graph.nodes.get_chat_model")
    def test_invoke_chain_uses_aux_role(self, mock_get):
        mock_llm = mock_get.return_value
        with patch("app.agent.graph.nodes.run_with_timeout", return_value=type("R", (), {"content": '{"blocked": false}'})()):
            from app.agent.graph.nodes import _invoke_chain
            from app.agent.prompts.rag_prompts import guard_prompt

            _invoke_chain(guard_prompt, {"question": "hi"}, label="guard")
        mock_get.assert_called_with(role="aux")
