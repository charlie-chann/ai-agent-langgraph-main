"""个人记忆 Agent - 核心业务逻辑"""

import re
from pathlib import Path
from typing import Generator
import sys

sys.path.insert(0, str(Path(__file__).parent))

from config import (
    OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE,
    MAX_SEARCH_RESULTS, MEMORY_TYPES, IMPORTANCE_LEVELS
)
from tools.memory_store import (
    MemoryEntry,
    create_memory, get_memory, search_memories,
    update_memory, delete_memory, list_all_memories, get_memory_stats
)


def _sanitize_input(text: str) -> str:
    text = text.strip()
    text = re.sub(r"ignore\s+previous\s+instructions?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return text[:2000]


def run_remember(
    content: str,
    memory_type: str = "note",
    importance: str = "medium",
    tags: list[str] | None = None
) -> dict:
    """保存一条新记忆"""
    content = _sanitize_input(content)
    if not content:
        return {"success": False, "error": "内容不能为空", "memory": None}

    try:
        entry = create_memory(content, memory_type, importance, tags)
        return {
            "success": True,
            "memory": entry,
            "id": entry.id,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e), "memory": None}


def run_recall(
    query: str,
    memory_type: str | None = None,
    importance: str | None = None,
    tags: list[str] | None = None,
    max_results: int = MAX_SEARCH_RESULTS
) -> dict:
    """检索记忆"""
    query = _sanitize_input(query)
    try:
        results = search_memories(query, memory_type, importance, tags, max_results)
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "error": None
        }
    except Exception as e:
        return {"success": False, "results": [], "count": 0, "error": str(e)}


def run_forget(memory_id: str) -> dict:
    """删除指定记忆"""
    memory_id = memory_id.strip()[:20]
    deleted = delete_memory(memory_id)
    return {"success": deleted, "id": memory_id}


def run_update(
    memory_id: str,
    content: str | None = None,
    importance: str | None = None,
    tags: list[str] | None = None
) -> dict:
    """更新记忆内容"""
    memory_id = memory_id.strip()[:20]
    if content:
        content = _sanitize_input(content)
    entry = update_memory(memory_id, content, importance, tags)
    if entry:
        return {"success": True, "memory": entry}
    return {"success": False, "error": f"未找到 ID: {memory_id}"}


def run_list_memories(limit: int = 50) -> dict:
    """列出所有记忆"""
    entries = list_all_memories(limit)
    return {"success": True, "memories": entries, "count": len(entries)}


def run_get_stats() -> dict:
    """获取记忆库统计"""
    return get_memory_stats()


def stream_chat(user_input: str) -> Generator[str, None, None]:
    """与记忆 Agent 的流式对话（可以记录/检索对话中的信息）"""
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
            "你是一位专业的个人助手，拥有持久化记忆能力。"
            "你能够记录用户说的重要信息，在需要时准确召回它们。"
            "你像一位贴心的秘书，帮助用户管理知识、任务、偏好和重要事项。"
            "当用户说'记住...'或'帮我记录...'时，提示用户可以使用记忆存储功能。"
        )),
        HumanMessage(content=user_input)
    ]
    for chunk in llm.stream(messages):
        if hasattr(chunk, "content") and chunk.content:
            yield chunk.content
