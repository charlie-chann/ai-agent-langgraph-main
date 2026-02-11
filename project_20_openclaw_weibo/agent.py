# agent.py — openclaw 微博内容 Agent
from __future__ import annotations

import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PLATFORM, DAILY_POST_LIMIT, OPTIMAL_POST_HOURS
from tools.content_generator import generate_weibo_post, generate_batch, WeiboPost
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags


_SYSTEM_PROMPT = """你是一个专业的微博内容运营 AI 助手。
你的职责是帮助用户：
1. 生成符合微博调性的高互动内容（简洁、接地气、有话题性）
2. 优化话题标签，提升内容曝光
3. 规划发布时间，在用户活跃峰值发布
4. 确保内容符合平台规范

注意：所有内容必须合法合规，不得包含违禁信息。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', str(text))
    return text[:2000]


def run_generate_post(topic: str, keywords: list[str] | None = None,
                      tone: str = "conversational") -> dict:
    """生成单条微博。"""
    post = generate_weibo_post(_sanitize(topic), keywords, tone)
    logger.info(f"微博生成 | 话题:{topic} | 字数:{post.word_count}")
    return post.to_dict()


def run_generate_batch(topic: str, count: int = 3) -> list[dict]:
    """批量生成微博内容。"""
    count = min(count, DAILY_POST_LIMIT)
    posts = generate_batch(_sanitize(topic), count)
    return [p.to_dict() for p in posts]


def run_optimize_tags(topic: str, keywords: list[str] | None = None) -> dict:
    """优化话题标签。"""
    return optimize_tags(PLATFORM, _sanitize(topic), keywords).to_dict()


def run_plan_schedule(posts_content: list[str]) -> dict:
    """规划发布时间表。"""
    return plan_schedule(PLATFORM, posts_content, OPTIMAL_POST_HOURS, DAILY_POST_LIMIT).to_dict()


def stream_chat(user_message: str, history: list[dict] | None = None):
    """流式 AI 对话。"""
    user_message = _sanitize(user_message)
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=user_message)]
    for chunk in llm.stream(messages):
        yield chunk.content
