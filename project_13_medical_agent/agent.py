# agent.py — 医疗辅助 Agent（LangGraph）
from __future__ import annotations

import re
import time
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, MASK_PII
from tools.symptom_checker import triage, TriageResult
from tools.appointment_tool import book_appointment, cancel_appointment, query_appointment
from tools.ehr_summary import summarize_ehr


_SYSTEM_PROMPT = """你是一个专业的医疗辅助助手。你的职责包括：
1. 根据患者描述的症状进行初步分诊，判断紧急程度
2. 协助预约合适的门诊科室
3. 快速生成电子健康档案摘要，方便医生快速了解患者情况

重要提示：
- 你提供的是辅助信息，不能替代专业医生诊断
- 在紧急情况下，应立即建议拨打120或前往急诊
- 严格保护患者隐私，不存储或透露个人信息
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize_input(text: str) -> str:
    """清洗用户输入，防止注入攻击。"""
    # 移除控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 截断超长输入
    return text[:2000]


def run_triage(symptoms_text: str) -> dict:
    """执行症状分诊。"""
    symptoms_text = _sanitize_input(symptoms_text)
    t0 = time.perf_counter()
    result = triage(symptoms_text, mask_pii=MASK_PII)
    elapsed = time.perf_counter() - t0
    logger.info(f"分诊完成 | 紧急度: {result.urgency_level} | 耗时: {elapsed:.2f}s")
    return result.to_dict()


def run_book_appointment(patient_id: str, department: str,
                         preferred_date: str | None = None,
                         notes: str = "") -> dict:
    """执行预约操作。"""
    patient_id = _sanitize_input(patient_id)
    department = _sanitize_input(department)
    t0 = time.perf_counter()
    appt = book_appointment(patient_id, department, preferred_date, notes)
    elapsed = time.perf_counter() - t0
    logger.info(f"预约成功 | ID: {appt.appointment_id} | 科室: {department} | 耗时: {elapsed:.2f}s")
    return appt.to_dict()


def run_ehr_summary(patient_id: str, raw_record: str) -> dict:
    """生成 EHR 摘要。"""
    patient_id = _sanitize_input(patient_id)
    raw_record = _sanitize_input(raw_record)
    t0 = time.perf_counter()
    summary = summarize_ehr(patient_id, raw_record)
    elapsed = time.perf_counter() - t0
    logger.info(f"EHR 摘要生成完成 | 患者ID: {patient_id} | 耗时: {elapsed:.2f}s")
    return summary.to_dict()


def chat(user_message: str, history: list[dict] | None = None) -> str:
    """
    与医疗助手对话（非流式）。

    Args:
        user_message: 用户输入
        history: 对话历史列表，格式 [{"role": "user/assistant", "content": "..."}]

    Returns:
        str: 助手回复
    """
    user_message = _sanitize_input(user_message)
    llm = _llm()

    messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    for h in (history or []):
        if h.get("role") == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h.get("role") == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))

    response = llm.invoke(messages)
    return response.content


def stream_chat(user_message: str, history: list[dict] | None = None):
    """流式对话生成器。"""
    user_message = _sanitize_input(user_message)
    llm = _llm()

    messages = [SystemMessage(content=_SYSTEM_PROMPT)]
    for h in (history or []):
        if h.get("role") == "user":
            messages.append(HumanMessage(content=h["content"]))
        elif h.get("role") == "assistant":
            messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))

    for chunk in llm.stream(messages):
        yield chunk.content
