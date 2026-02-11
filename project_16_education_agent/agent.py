# agent.py — 个性化教育 Agent
from __future__ import annotations
import re
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
from tools.study_planner import generate_study_plan, generate_quiz, score_quiz

_SYSTEM_PROMPT = "你是一个专业的 AI 教育助手，帮助学生制定学习计划、提供练习题和学习指导。"

def _llm(): return ChatOllama(model=DEFAULT_MODEL, base_url=OLLAMA_BASE_URL, temperature=TEMPERATURE)
def _sanitize(t): return re.sub(r'[\x00-\x1f\x7f]', '', t)[:2000]

def run_generate_plan(student: str, subject: str, level: str = "beginner",
                      daily_min: int = 60, days: int = 30) -> dict:
    plan = generate_study_plan(_sanitize(student), _sanitize(subject), level, daily_min, days)
    return plan.to_dict()

def run_quiz(subject: str, topic: str | None = None, difficulty: str = "medium", count: int = 3) -> list:
    return generate_quiz(_sanitize(subject), topic, difficulty, count)

def run_score(questions: list, answers: dict) -> dict:
    return score_quiz(questions, answers)

def stream_chat(user_message: str, history: list | None = None):
    llm = _llm()
    messages = [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=_sanitize(user_message))]
    for chunk in llm.stream(messages):
        yield chunk.content
