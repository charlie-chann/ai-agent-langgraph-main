# agent.py — 运维故障根因分析 Agent
from __future__ import annotations
import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.log_analyzer import analyze_logs, parse_logs

_SYSTEM_PROMPT = "你是一个专业的运维 AI 助手，擅长日志分析、故障诊断和根因定位，提供简洁可操作的修复建议。"

def _llm(): return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)
def _sanitize(t): return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(t))[:50000]

def run_analyze_logs(log_text: str) -> dict:
    return analyze_logs(_sanitize(log_text)).to_dict()

def stream_chat(user_message: str, history: list | None = None):
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=_sanitize(user_message))]
    for chunk in llm.stream(messages):
        yield chunk.content
