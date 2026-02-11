"""
tools/search_tool.py — DuckDuckGo 网络搜索工具

【职责】
1. 提供 web_search @tool，查询实时网页信息（新闻、价格、文档等）
2. 无需 API Key，使用 DuckDuckGo 免费搜索

【设计原因】
1. LLM 知识有截止日期，时事/价格必须联网
2. parse_docstring=True：LangChain 会解析 Args/Returns 段，丰富参数说明
3. 输入截断 500 字符、结果条数由 config.MAX_SEARCH_RESULTS 控制
"""
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from loguru import logger

from config import settings, MAX_SEARCH_RESULTS


@tool(parse_docstring=True)
def web_search(query: str) -> str:
    """Search the web for current information using DuckDuckGo.

    Use this tool when you need to:
    - Find current events, news, or prices
    - Look up facts or documentation
    - Get information about recent developments
    - Search for specific terms or phrases online

    Args:
        query: The search query. Be specific and use quotes for exact phrases.

    Returns:
        Search results from DuckDuckGo, including titles and snippets.
        Returns "No results found." if nothing matches.
    """
    # 基础输入清洗：去空白、限制长度
    query = str(query).strip()[:500]
    if not query:
        return "Error: empty search query"

    try:
        # DuckDuckGoSearchRun 封装了 DDG API 变更，比直接调 HTTP 更稳
        search = DuckDuckGoSearchRun(max_results=MAX_SEARCH_RESULTS)
        logger.info(f"[web_search] query={query!r}")
        result = search.run(query)
        return result if result else "No results found."
    except Exception as e:
        logger.error(f"[web_search] failed: {e}")
        return f"Search failed: {e}"
