"""
tools/search_tool.py — DuckDuckGo 网络搜索工具

【职责】
1. 封装 DuckDuckGoSearchRun，为 Researcher 节点提供实时网页检索能力
2. 提供单次搜索 web_search 与批量 multi_search，支持多研究问题并行检索
3. 统一错误处理与日志，搜索失败时返回可读错误信息而非抛异常

【设计原因】
1. 模块级单例 _search：避免每次查询重复实例化 DuckDuckGo 客户端
2. 查询长度截断 500 字符：防止异常长输入导致 API 超时或无效请求
3. multi_search 上限 4 条：平衡 Researcher 信息覆盖与 API 调用成本/延迟
4. 异常吞并返回字符串：多 Agent 流水线不因单次搜索失败而整体中断
"""
from langchain_community.tools import DuckDuckGoSearchRun
from loguru import logger

from config import MAX_SEARCH_RESULTS

# 进程级搜索客户端单例，max_results 由配置统一控制
_search = DuckDuckGoSearchRun(max_results=MAX_SEARCH_RESULTS)


def web_search(query: str) -> str:
    """
    执行单次 DuckDuckGo 网页搜索。

    参数:
        query: 搜索关键词或自然语言问句

    返回:
        搜索结果文本；空查询 / 无结果 / 异常时返回对应提示字符串

    流程:
        1. 清洗并截断 query
        2. 调用 _search.run
        3. 记录日志；异常时返回 "Search unavailable: ..."
    """
    query = query.strip()[:500]
    if not query:
        return "No query provided."
    try:
        logger.info(f"[search] {query!r}")
        result = _search.run(query)
        return result or "No results found."
    except Exception as e:
        logger.error(f"[search] failed: {e}")
        return f"Search unavailable: {e}"


def multi_search(questions: list[str]) -> str:
    """
    对多个研究问题依次搜索，合并为一份 Markdown 格式文本。

    参数:
        questions: 研究问题列表（通常来自 Planner 的 research_questions）

    返回:
        各次搜索以 `### Search N:` 分隔拼接的字符串，供 Researcher Prompt 使用

    流程:
        最多取前 4 个问题 → 逐个 web_search → 用双换行拼接
    """
    combined = []
    for i, q in enumerate(questions[:4], 1):  # cap at 4 searches
        result = web_search(q)
        combined.append(f"### Search {i}: {q}\n{result}")
    return "\n\n".join(combined)
