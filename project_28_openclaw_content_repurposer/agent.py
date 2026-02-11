"""内容二次加工 Agent - 核心业务逻辑"""

import re
from pathlib import Path
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    PLATFORM_SPECS, DEFAULT_TARGET_PLATFORMS
)
from tools.content_adapter import (
    repurpose_for_platform, repurpose_for_all_platforms,
    AdaptedContent, _sanitize_text
)


def _sanitize_input(text: str) -> str:
    text = text.strip()
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:2000]


def run_repurpose(
    content: str,
    topic: str,
    platforms: list[str] | None = None
) -> dict:
    """
    将内容二次加工为多平台版本。
    
    Returns: {
        success, platforms_adapted, results, compliance_summary, error
    }
    """
    content = _sanitize_input(content)
    topic = _sanitize_input(topic)[:100]

    if not content:
        return {"success": False, "error": "内容不能为空", "results": {}}
    if not topic:
        return {"success": False, "error": "话题不能为空", "results": {}}

    try:
        adapted = repurpose_for_all_platforms(content, topic, platforms)
        compliance_summary = {
            platform: result.compliant
            for platform, result in adapted.items()
        }
        return {
            "success": True,
            "platforms_adapted": list(adapted.keys()),
            "results": adapted,
            "compliance_summary": compliance_summary,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e), "results": {}}


def run_repurpose_single(content: str, topic: str, platform: str) -> dict:
    """将内容适配为单个平台"""
    content = _sanitize_input(content)
    topic = _sanitize_input(topic)[:100]

    if platform not in PLATFORM_SPECS:
        return {
            "success": False,
            "error": f"不支持的平台: {platform}。支持: {list(PLATFORM_SPECS.keys())}",
            "result": None
        }

    adapted = repurpose_for_platform(content, topic, platform)
    if not adapted:
        return {"success": False, "error": "适配失败", "result": None}

    return {
        "success": True,
        "result": adapted,
        "platform": platform,
        "compliant": adapted.compliant,
        "char_count": adapted.char_count
    }


def run_get_platform_specs(platform: str | None = None) -> dict:
    """获取平台规格说明"""
    if platform:
        return PLATFORM_SPECS.get(platform, {})
    return PLATFORM_SPECS


def run_compliance_check(content: str, platform: str) -> dict:
    """检查内容是否符合平台规范"""
    content = _sanitize_input(content)
    if platform not in PLATFORM_SPECS:
        return {"compliant": False, "error": f"未知平台: {platform}"}

    spec = PLATFORM_SPECS[platform]
    char_count = len(content)
    compliant = char_count <= spec["max_chars"]

    return {
        "platform": platform,
        "char_count": char_count,
        "max_chars": spec["max_chars"],
        "compliant": compliant,
        "chars_over": max(0, char_count - spec["max_chars"])
    }


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与内容加工 Agent 的流式对话"""
    from langchain_community.chat_models import ChatOllama
    from langchain.schema import HumanMessage, SystemMessage

    user_input = _sanitize_input(user_input[:500])
    llm = ChatOllama(
        model=DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE
    )
    messages = [
        SystemMessage(content=(
            "你是一位专业的内容创作顾问，擅长将内容适配到不同社交媒体平台。"
            "微博、小红书、知乎、抖音、Twitter等各平台有不同的内容风格和规范。"
            "你能够提供专业的内容改写建议。"
        )),
        HumanMessage(content=user_input)
    ]
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
