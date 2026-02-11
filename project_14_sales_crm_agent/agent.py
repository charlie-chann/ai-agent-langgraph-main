# agent.py — 销售 CRM Agent
from __future__ import annotations

import re
import time
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.lead_scorer import Lead, score_lead
from tools.email_generator import generate_email
from tools.crm_tool import (
    create_lead, update_lead_status, log_activity,
    get_lead, list_leads_by_status, pipeline_summary
)


_SYSTEM_PROMPT = """你是一个专业的销售 CRM 智能助手，帮助销售团队：
1. 对销售线索进行智能评分和优先级排序
2. 自动生成个性化销售邮件
3. 跟踪和管理客户互动记录
4. 分析销售漏斗，提供跟进建议

你的回复应简洁专业，以结果为导向，帮助销售人员提升效率。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize_input(text: str) -> str:
    """清洗用户输入，防止注入攻击。"""
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text[:3000]


def run_lead_scoring(lead_data: dict) -> dict:
    """对线索进行评分。"""
    lead = Lead(
        lead_id=lead_data.get("lead_id", "TEMP-001"),
        name=lead_data.get("name", ""),
        company=lead_data.get("company", ""),
        title=lead_data.get("title", ""),
        industry=lead_data.get("industry", "其他"),
        budget=float(lead_data.get("budget", 0)),
        timeline_days=int(lead_data.get("timeline_days", 90)),
        engagement_score=int(lead_data.get("engagement_score", 0)),
        last_contact_date=lead_data.get("last_contact_date", ""),
    )
    t0 = time.perf_counter()
    score_result = score_lead(lead)
    elapsed = time.perf_counter() - t0
    logger.info(f"线索评分 | ID: {lead.lead_id} | 分数: {score_result.total_score} | 耗时: {elapsed:.2f}s")
    return score_result.to_dict()


def run_generate_email(email_type: str, to_name: str, to_company: str,
                       industry: str, **kwargs) -> dict:
    """生成销售邮件。"""
    to_name = _sanitize_input(to_name)
    to_company = _sanitize_input(to_company)
    email = generate_email(email_type, to_name, to_company, industry, **kwargs)
    return email.to_dict()


def run_create_lead(name: str, company: str, email: str, phone: str,
                    tags: list[str] | None = None) -> dict:
    """创建 CRM 线索。"""
    record = create_lead(name, company, email, phone, tags)
    return record.to_dict()


def chat(user_message: str, history: list[dict] | None = None) -> str:
    """与 CRM 助手对话（非流式）。"""
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
