# agent.py — openclaw Twitter/X 内容 Agent
from __future__ import annotations

import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PLATFORM, DAILY_POST_LIMIT, OPTIMAL_POST_HOURS_UTC
from tools.content_generator import generate_tweet, generate_thread, Tweet, TwitterThread
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags

_SYSTEM_PROMPT = """You are a professional Twitter/X content strategy AI assistant.
Your responsibilities:
1. Generate high-engagement tweets and threads (concise, value-packed, conversation-starting)
2. Optimize hashtags (max 3 per tweet — Twitter algorithm penalizes hashtag stuffing)
3. Plan posting schedule around US peak hours (UTC timing)
4. Ensure content compliance — no spam, misleading claims, or prohibited content

Key rules: Tweets ≤ 280 chars. Threads: hook → value → CTA structure.
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', str(text))
    return re.sub(r'<[^>]+>', '', text)[:2000]


def run_generate_tweet(topic: str, keywords: list[str] | None = None,
                       style: str = "informative") -> dict:
    """生成单条推文。"""
    tweet = generate_tweet(_sanitize(topic), keywords, style)
    logger.info(f"Tweet generated | topic:{topic} | chars:{tweet.char_count}")
    return tweet.to_dict()


def run_generate_thread(topic: str, points: list[str] | None = None,
                        num_tweets: int = 5) -> dict:
    """生成推文线程。"""
    thread = generate_thread(_sanitize(topic), points, num_tweets)
    logger.info(f"Thread generated | topic:{topic} | tweets:{thread.total_tweets}")
    return thread.to_dict()


def run_optimize_tags(topic: str, keywords: list[str] | None = None) -> dict:
    """优化标签。"""
    return optimize_tags(PLATFORM, _sanitize(topic), keywords).to_dict()


def run_plan_schedule(posts_content: list[str]) -> dict:
    """规划发布时间表（UTC）。"""
    return plan_schedule(PLATFORM, posts_content, OPTIMAL_POST_HOURS_UTC, DAILY_POST_LIMIT).to_dict()


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
