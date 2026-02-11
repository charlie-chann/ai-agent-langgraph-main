# tools/search_tool.py — web search for project_03
from langchain_community.tools import DuckDuckGoSearchRun
from loguru import logger

from config import MAX_SEARCH_RESULTS

_search = DuckDuckGoSearchRun(max_results=MAX_SEARCH_RESULTS)


def web_search(query: str) -> str:
    """Search the web and return results as text."""
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
    """Run multiple searches and return combined results."""
    combined = []
    for i, q in enumerate(questions[:4], 1):  # cap at 4 searches
        result = web_search(q)
        combined.append(f"### Search {i}: {q}\n{result}")
    return "\n\n".join(combined)
