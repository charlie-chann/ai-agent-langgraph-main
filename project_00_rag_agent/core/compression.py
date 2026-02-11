"""
core/compression.py — 对话历史与 RAG 上下文压缩

【职责】
1. compress_chat_history：多轮对话滑动窗口 +  pinned 消息保留 + token 预算裁剪
2. trim_context_chunks：检索 chunk 按 token 预算拼接，防止 Prompt 超长
3. dict_history_to_messages：API 层 dict 格式历史转为 LangChain Message 列表

【设计原因】
1. LLM 上下文窗口有限，必须在注入 Prompt 前裁剪历史与 RAG 片段
2. 使用字符/heuristic 估算 token（~4 字符/token），避免依赖 tiktoken 等额外依赖
3. System 消息始终保留；超预算时优先丢弃最旧的非 system 消息

【与 project_01 差异】
project_01 直接将完整 chat_history 传入 Prompt；本模块新增压缩与 RAG 预算控制，
并支持 pinned_indices、kg_context 等生产场景下的上下文管理。
"""
from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from loguru import logger

from config import settings


def _estimate_tokens(text: str) -> int:
    """
    粗略估算文本 token 数。

    混合中英文场景按约 4 字符/token  heuristic；至少返回 1 避免空串除零。
    """
    # Rough heuristic: ~4 chars per token for mixed CN/EN
    return max(1, len(text) // 4)


def compress_chat_history(
    messages: List[BaseMessage],
    *,
    max_tokens: int = 4000,
    keep_last: int = settings.history_limit,
    pinned_indices: Optional[List[int]] = None,
) -> List[BaseMessage]:
    """
    压缩对话历史：保留 system + pinned + 最近 keep_last 条；超 max_tokens 则丢弃中间/最旧消息。

    pinned_indices 相对于「非 system 消息」列表的下标，用于固定重要上下文（如用户确认的规则）。
    """
    if not messages:
        return []

    pinned = set(pinned_indices or [])
    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    rest = [m for i, m in enumerate(messages) if not isinstance(m, SystemMessage)]

    kept: List[BaseMessage] = []
    for i, m in enumerate(rest):
        if i in pinned:
            kept.append(m)

    # 滑动窗口：保留最近 keep_last 条（与 pinned 去重合并）
    tail = rest[-keep_last:] if keep_last > 0 else []
    for m in tail:
        if m not in kept:
            kept.append(m)

    # 按原始顺序排序，保证多轮对话时间线正确
    order = {id(m): idx for idx, m in enumerate(rest)}
    kept.sort(key=lambda m: order.get(id(m), 0))

    combined = system_msgs + kept
    total = sum(_estimate_tokens(getattr(m, "content", "") or "") for m in combined)
    if total > max_tokens:
        logger.warning(f"History still {total} tokens after compression; trimming tail")
        while combined and total > max_tokens:
            # 从 combined 头部删除最旧的非 system 消息（system 指令不轻易丢）
            for idx, m in enumerate(combined):
                if not isinstance(m, SystemMessage):
                    combined.pop(idx)
                    break
            else:
                break
            total = sum(_estimate_tokens(getattr(m, "content", "") or "") for m in combined)
    return combined


def trim_context_chunks(chunks: List[str], max_tokens: int = settings.rag_context_max_tokens) -> str:
    """
    按 token 预算拼接检索 chunk；调用方应保证 chunks 已按相关性降序排列。

    超出预算时截断，不再加入后续 chunk；片段之间用 \\n\\n---\\n\\n 分隔。
    """
    parts: List[str] = []
    used = 0
    for chunk in chunks:
        cost = _estimate_tokens(chunk)
        if used + cost > max_tokens:
            break
        parts.append(chunk)
        used += cost
    return "\n\n---\n\n".join(parts)


def dict_history_to_messages(history: List[dict]) -> List[BaseMessage]:
    """
    将 API 请求体中的 {role, content} 列表转为 LangChain BaseMessage 列表。

    兼容 role 别名：user/human、assistant/ai、system。
    """
    out: List[BaseMessage] = []
    for item in history:
        role = item.get("role", "user")
        content = item.get("content", "")
        if role in ("user", "human"):
            out.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
    return out
