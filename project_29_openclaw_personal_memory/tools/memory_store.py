"""记忆存储工具 - 持久化记忆的 CRUD 操作"""

import re
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    MAX_MEMORY_ENTRIES, MAX_CONTENT_LENGTH, MEMORY_TYPES,
    IMPORTANCE_LEVELS, MEMORY_STORE_PATH, AUTO_TAG_KEYWORDS
)


@dataclass
class MemoryEntry:
    """单条记忆"""
    id: str
    content: str
    memory_type: str               # from MEMORY_TYPES
    importance: str                # from IMPORTANCE_LEVELS
    tags: list[str]
    created_at: str
    updated_at: str
    access_count: int = 0          # 被访问次数（影响记忆强度）
    last_accessed: str = ""


def _get_store_path() -> Path:
    store = Path(__file__).parent.parent / MEMORY_STORE_PATH
    store.mkdir(parents=True, exist_ok=True)
    return store / "memories.json"


def _load_all() -> list[MemoryEntry]:
    path = _get_store_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [MemoryEntry(**entry) for entry in data]
    except (json.JSONDecodeError, TypeError, KeyError):
        return []


def _save_all(entries: list[MemoryEntry]) -> None:
    path = _get_store_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in entries], f, ensure_ascii=False, indent=2)


def _auto_tag(content: str) -> list[str]:
    """根据内容自动添加关键词标签"""
    tags = []
    for tag, keywords in AUTO_TAG_KEYWORDS.items():
        if any(kw in content for kw in keywords):
            tags.append(tag)
    return tags


def _sanitize_content(content: str) -> str:
    content = re.sub(r"<[^>]+>", "", content)
    content = re.sub(r"\s+", " ", content).strip()
    return content[:MAX_CONTENT_LENGTH]


def create_memory(
    content: str,
    memory_type: str = "note",
    importance: str = "medium",
    tags: list[str] | None = None
) -> MemoryEntry:
    """创建新记忆条目"""
    content = _sanitize_content(content)
    if memory_type not in MEMORY_TYPES:
        memory_type = "note"
    if importance not in IMPORTANCE_LEVELS:
        importance = "medium"

    auto_tags = _auto_tag(content)
    all_tags = list(set((tags or []) + auto_tags))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = MemoryEntry(
        id=uuid.uuid4().hex[:8],
        content=content,
        memory_type=memory_type,
        importance=importance,
        tags=all_tags,
        created_at=now,
        updated_at=now,
        last_accessed=now
    )

    existing = _load_all()
    # 超过上限时移除最老的低重要度记忆
    if len(existing) >= MAX_MEMORY_ENTRIES:
        existing = sorted(existing, key=lambda e: (e.importance == "low", e.created_at))
        existing = existing[-MAX_MEMORY_ENTRIES + 1:]

    existing.append(entry)
    _save_all(existing)
    return entry


def get_memory(memory_id: str) -> MemoryEntry | None:
    """按 ID 获取记忆"""
    entries = _load_all()
    for entry in entries:
        if entry.id == memory_id:
            entry.access_count += 1
            entry.last_accessed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _save_all(entries)
            return entry
    return None


def search_memories(
    query: str,
    memory_type: str | None = None,
    importance: str | None = None,
    tags: list[str] | None = None,
    max_results: int = 10
) -> list[MemoryEntry]:
    """搜索记忆（基于关键词匹配 + 类型/重要性过滤）"""
    query = re.sub(r"\s+", " ", query.strip().lower())
    entries = _load_all()
    results = []

    for entry in entries:
        # 类型过滤
        if memory_type and entry.memory_type != memory_type:
            continue
        # 重要性过滤
        if importance and entry.importance != importance:
            continue
        # 标签过滤
        if tags and not any(t in entry.tags for t in tags):
            continue
        # 关键词匹配
        if query and query not in entry.content.lower() and not any(
            q in entry.content.lower() for q in query.split()
        ):
            continue
        results.append(entry)

    # 按重要性 + 访问次数排序
    importance_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    results.sort(key=lambda e: (importance_order.get(e.importance, 0), e.access_count), reverse=True)
    return results[:max_results]


def update_memory(
    memory_id: str,
    content: str | None = None,
    importance: str | None = None,
    tags: list[str] | None = None
) -> MemoryEntry | None:
    """更新记忆条目"""
    entries = _load_all()
    for entry in entries:
        if entry.id == memory_id:
            if content:
                entry.content = _sanitize_content(content)
            if importance and importance in IMPORTANCE_LEVELS:
                entry.importance = importance
            if tags is not None:
                entry.tags = tags
            entry.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _save_all(entries)
            return entry
    return None


def delete_memory(memory_id: str) -> bool:
    """删除记忆条目"""
    entries = _load_all()
    new_entries = [e for e in entries if e.id != memory_id]
    if len(new_entries) < len(entries):
        _save_all(new_entries)
        return True
    return False


def list_all_memories(limit: int = 50) -> list[MemoryEntry]:
    """列出所有记忆（按创建时间倒序）"""
    entries = _load_all()
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


def get_memory_stats() -> dict:
    """获取记忆库统计信息"""
    entries = _load_all()
    type_counts = {t: 0 for t in MEMORY_TYPES}
    importance_counts = {i: 0 for i in IMPORTANCE_LEVELS}
    for e in entries:
        type_counts[e.memory_type] = type_counts.get(e.memory_type, 0) + 1
        importance_counts[e.importance] = importance_counts.get(e.importance, 0) + 1

    return {
        "total": len(entries),
        "by_type": type_counts,
        "by_importance": importance_counts,
        "capacity_used": f"{len(entries)}/{MAX_MEMORY_ENTRIES}"
    }
