# agent.py — openclaw 小红书内容 Agent
from __future__ import annotations

import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PLATFORM, DAILY_POST_LIMIT, OPTIMAL_POST_HOURS
from tools.content_generator import generate_xiaohongshu_post, XiaohongshuPost
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags

_SYSTEM_PROMPT = """你是一个专业的小红书内容运营 AI 助手。
你的职责是帮助用户：
1. 生成符合小红书调性的高互动图文笔记（标题吸睛、内容有用、配图建议专业）
2. 优化话题标签，提升笔记曝光和涨粉效果
3. 规划发布时间，在用户活跃峰值发布
4. 确保内容合规，无违禁词

注意：内容必须真实、有价值，不虚假宣传。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', str(text))
    return re.sub(r'<[^>]+>', '', text)[:2000]


def run_generate_post(topic: str, keywords: list[str] | None = None, style: str = "lifestyle") -> dict:
    """生成小红书笔记。"""
    post = generate_xiaohongshu_post(_sanitize(topic), keywords, style)
    logger.info(f"小红书生成 | 话题:{topic} | 字数:{post.word_count}")
    return post.to_dict()


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
