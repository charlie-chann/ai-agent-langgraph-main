# agent.py — openclaw 抖音内容 Agent
from __future__ import annotations

import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, PLATFORM, DAILY_POST_LIMIT, OPTIMAL_POST_HOURS
from tools.content_generator import generate_douyin_script, DouyinScript
from tools.schedule_tool import plan_schedule, calculate_best_time
from tools.tag_optimizer import optimize_tags

_SYSTEM_PROMPT = """你是一个专业的抖音内容运营 AI 助手。
你的职责是帮助用户：
1. 生成符合抖音调性的视频脚本（开场3秒必须吸睛、内容有节奏感、结尾有行动引导）
2. 优化话题标签，借助算法推流提升曝光
3. 规划发布时间，在流量高峰期发布
4. 确保内容合规，无违禁词

注意：抖音视频要"快、准、爆"，开场必须抓住用户眼球。
"""


def _llm() -> ChatOllama:
    return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)


def _sanitize(text: str) -> str:
    text = re.sub(r'[\x00-\x1f\x7f]', '', str(text))
    return re.sub(r'<[^>]+>', '', text)[:2000]


def run_generate_script(topic: str, keywords: list[str] | None = None,
                        duration: int = 60, style: str = "educational") -> dict:
    """生成抖音视频脚本。"""
    script = generate_douyin_script(_sanitize(topic), keywords, duration, style)
    logger.info(f"抖音脚本生成 | 话题:{topic} | 时长:{duration}s")
    return script.to_dict()


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
