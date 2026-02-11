"""
步骤 4b：LLM-as-Judge 离线打分

读取 eval/prompts/judge_faithfulness.txt，对 (question, context, answer) 评分。
Ollama 不可用时返回 skipped，不影响规则分主流程。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .paths import PROMPTS_DIR, RAG_PROJECT


def _parse_judge_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    return {"pass": False, "score": 0.0, "reason": "judge parse failed"}


def llm_judge(question: str, context: str, answer: str) -> dict[str, Any]:
    judge_file = PROMPTS_DIR / "judge_faithfulness.txt"
    template = judge_file.read_text(encoding="utf-8")
    prompt = template.format(question=question, context=context[:3000], answer=answer[:2000])

    rag_root = str(RAG_PROJECT)
    if rag_root not in sys.path:
        sys.path.insert(0, rag_root)

    try:
        from langchain_ollama import ChatOllama
        from langchain_core.messages import HumanMessage
        from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE

        llm = ChatOllama(
            model=DEFAULT_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=min(TEMPERATURE, 0.1),
        )
        resp = llm.invoke([HumanMessage(content=prompt)])
        data = _parse_judge_json(resp.content if isinstance(resp.content, str) else str(resp.content))
        return {
            "judge_pass": bool(data.get("pass", False)),
            "judge_score": float(data.get("score", 0.0)),
            "judge_reason": data.get("reason", ""),
            "judge_skipped": False,
        }
    except Exception as e:
        return {
            "judge_pass": None,
            "judge_score": None,
            "judge_reason": f"judge skipped: {e}",
            "judge_skipped": True,
        }
