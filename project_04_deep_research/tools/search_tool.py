"""
tools/search_tool.py — 研究级 Web 搜索工具

【职责】
封装 DuckDuckGo 网络搜索，提供单条查询、批量查询及结果格式化能力，
供 Deep Research Agent 在迭代搜索循环中调用。

【设计原因】
搜索逻辑与 Agent 图节点解耦，便于替换搜索引擎或添加缓存层；
ImportError 降级保证在无 langchain_community 依赖时仍可运行演示。
"""
from __future__ import annotations
import time
from loguru import logger

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    # 单例搜索实例，max_results=5 平衡信息量与 token 消耗
    _search = DuckDuckGoSearchRun(max_results=5)

    def web_search(query: str) -> str:
        """
        执行单条 Web 搜索。

        Args:
            query: 搜索关键词或自然语言查询

        Returns:
            搜索结果文本；失败或空查询时返回提示信息
        """
        # 截断过长查询，避免 API 拒绝或 token 溢出
        query = query.strip()[:500]
        if not query:
            return "Empty query."
        try:
            time.sleep(0.5)  # 礼貌性限速，降低被搜索引擎封禁的风险
            result = _search.run(query)
            return result or "No results."
        except Exception as e:
            logger.warning(f"Search failed for {query!r}: {e}")
            return f"Search unavailable: {e}"

except ImportError:
    # 依赖缺失时的降级实现，便于 CI/离线环境运行
    def web_search(query: str) -> str:
        """
        降级版 Web 搜索（依赖不可用时）。

        Args:
            query: 搜索关键词

        Returns:
            占位提示字符串
        """
        return f"[Search unavailable] Would search: {query}"


def batch_search(queries: list[str]) -> dict[str, str]:
    """
    批量执行多条搜索查询。

    Args:
        queries: 查询字符串列表

    Returns:
        字典，键为查询、值为对应搜索结果
    """
    results = {}
    for q in queries[:6]:  # 每轮最多 6 条，防止请求过多拖慢流水线
        logger.info(f"[search] {q!r}")
        results[q] = web_search(q)
    return results


def format_search_results(results: dict[str, str]) -> str:
    """
    将批量搜索结果格式化为可读 Markdown 块，供 Synthesizer 节点消费。

    Args:
        results: batch_search 返回的 {query: result} 字典

    Returns:
        按序号分节的 Markdown 字符串
    """
    parts = []
    for i, (q, r) in enumerate(results.items(), 1):
        parts.append(f"### Search {i}: {q}\n{r}")
    return "\n\n".join(parts)
