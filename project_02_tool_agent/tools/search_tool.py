# tools/search_tool.py — DuckDuckGo web search (no API key required)
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
    # Basic input sanitization
    query = str(query).strip()[:500]
    if not query:
        return "Error: empty search query"
    
    try:
        # Use DuckDuckGoSearchRun (handles API changes internally)
        search = DuckDuckGoSearchRun(max_results=MAX_SEARCH_RESULTS)
        logger.info(f"[web_search] query={query!r}")
        result = search.run(query)
        return result if result else "No results found."
    except Exception as e:
        logger.error(f"[web_search] failed: {e}")
        return f"Search failed: {e}"
