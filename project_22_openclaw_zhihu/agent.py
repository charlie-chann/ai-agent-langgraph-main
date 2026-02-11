# agent.py — openclaw 知乎内容 Agent
from __future__ import annotations

import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PLATFORM, DAILY_POST_LIMIT, OPTIMAL_POST_HOURS
from tools.content_generator import generate_zhihu_answer, ZhihuContent
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags

_SYSTEM_PROMPT = """你是一个专业的知乎内容运营 AI 助手。
你的职责是帮助用户：
1. 生成高质量的知乎回答（逻辑严谨、有深度、有数据支撑）
2. 优化话题标签，提升内容曝光
3. 规划发布时间，在用户活跃峰值发布
4. 确保内容合规，无违禁词

注意：知乎用户偏好专业、深度、有洞见的内容。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', str(text))
    return re.sub(r'<[^>]+>', '', text)[:2000]


def run_generate_answer(question: str, topic: str = "科技",
                        expertise_level: str = "intermediate") -> dict:
    """生成知乎回答。"""
    content = generate_zhihu_answer(_sanitize(question), _sanitize(topic), expertise_level)
    logger.info(f"知乎生成 | 问题:{question} | 字数:{content.word_count}")
    return content.to_dict()


def run_optimize_tags(topic: str, keywords: list[str] | None = None) -> dict:
    """优化话题标签。"""
    return optimize_tags(PLATFORM, _sanitize(topic), keywords).to_dict()


def run_plan_schedule(posts_content: list[str]) -> dict:
    """规划发布时间表。"""
    return plan_schedule(PLATFORM, posts_content, OPTIMAL_POST_HOURS, DAILY_POST_LIMIT).to_dict()


def run_get_best_time() -> dict:
    """获取最佳发布时间建议。"""
    return calculate_best_time(PLATFORM)


def stream_chat(user_message: str):
    """流式 AI 对话。"""
    user_message = _sanitize(user_message)
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_message)]
    for chunk in llm.stream(messages):
        yield chunk.content
