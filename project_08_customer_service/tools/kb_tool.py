# tools/kb_tool.py — 知识库BM25搜索工具
"""
基于BM25的知识库全文搜索工具。
从 knowledge_base/faq.json 加载FAQ，支持关键词匹配检索。
"""
from __future__ import annotations

import json
from pathlib import Path
from langchain_core.tools import tool
from loguru import logger

from config import KB_DIR, MAX_KB_RESULTS

# Use path relative to this file's location, not CWD
_KB_PATH = Path(__file__).parent.parent / KB_DIR / "faq.json"

def _load_kb() -> list[dict]:
    """加载知识库JSON文件，返回文章列表。"""
    if not _KB_PATH.exists():
        return []
    with open(_KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _tokenize(text: str) -> set[str]:
    """将查询拆分为词元：英文按空格分词，中文额外提取双字符bigram。"""
    tokens = set(text.lower().split())
    # 中文bigram：对连续中文字符提取2-gram（词粒度搜索）
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        for i in range(len(chars) - 1):
            tokens.add(chars[i] + chars[i + 1])
    return tokens


def _bm25_score(query: str, document: dict) -> float:
    """
    简化版BM25评分：统计查询词在文档中的出现频率。
    中文查询使用bigram分词；实际生产可替换为 rank_bm25 库。
    """
    query_words = _tokenize(query)
    # 合并所有可搜索文本
    text = " ".join([
        document.get("question", ""),
        document.get("answer", ""),
        document.get("category", ""),
        " ".join(document.get("tags", [])),
    ]).lower()

    score = 0.0
    for word in query_words:
        count = text.count(word)
        if count > 0:
            score += 1 + 0.5 * (count - 1)  # 频率饱和函数
    # 对问题字段命中加权
    if any(w in document.get("question", "").lower() for w in query_words):
        score += 2.0
    return score


@tool
def search_kb(query: str) -> str:
    """在知识库中搜索与用户问题相关的FAQ。
    输入：用户问题或关键词（中文/英文均可）
    输出：最相关的FAQ条目（JSON格式，最多3条）
    """
    query = query.strip()
    if not query:
        return "查询内容不能为空"

    articles = _load_kb()
    if not articles:
        return "知识库暂未初始化，请联系管理员"

    # 对所有文章打分并排序
    scored = [(a, _bm25_score(query, a)) for a in articles]
    scored.sort(key=lambda x: x[1], reverse=True)

    # 只返回有得分的结果
    top = [(a, s) for a, s in scored[:MAX_KB_RESULTS] if s > 0]
    if not top:
        return json.dumps({"found": False, "message": "未找到相关知识库内容，建议创建工单"}, ensure_ascii=False)

    results = []
    for article, score in top:
        results.append({
            "id": article["id"],
            "category": article["category"],
            "question": article["question"],
            "answer": article["answer"],
            "relevance_score": round(score, 2),
        })

    logger.info(f"[kb_search] query={query!r} hits={len(results)}")
    return json.dumps({"found": True, "results": results}, ensure_ascii=False, indent=2)


@tool
def list_kb_categories() -> str:
    """列出知识库中所有分类。
    输出：JSON格式的分类列表及每个分类的文章数量。
    """
    articles = _load_kb()
    categories: dict[str, int] = {}
    for a in articles:
        cat = a.get("category", "未分类")
        categories[cat] = categories.get(cat, 0) + 1
    return json.dumps({
        "total_articles": len(articles),
        "categories": categories,
    }, ensure_ascii=False, indent=2)
