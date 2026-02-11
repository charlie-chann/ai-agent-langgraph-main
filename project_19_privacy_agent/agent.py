# agent.py — 本地隐私 Agent
from __future__ import annotations
import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PII_DETECTION_ENABLED
from tools.pii_detector import detect_and_mask, audit_log

_SYSTEM_PROMPT = """你是一个注重隐私保护的本地 AI 助手，所有数据处理在本地完成，不泄露任何敏感信息。
你优先保护用户隐私，在回答问题前会检测并脱敏 PII 数据。"""

def _llm(): return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)
def _sanitize(t): return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', str(t))[:50000]

def run_pii_scan(text: str, mask: bool = True) -> dict:
    return detect_and_mask(_sanitize(text), mask).to_dict()

def stream_chat(user_message: str, history: list | None = None):
    user_message = _sanitize(user_message)
    if PII_DETECTION_ENABLED:
        pii_result = detect_and_mask(user_message, mask=True)
        user_message = pii_result.masked_text
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_message)]
    for chunk in llm.stream(messages):
        yield chunk.content
