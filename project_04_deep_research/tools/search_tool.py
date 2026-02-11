# tools/search_tool.py — research-grade web search for project_04
from __future__ import annotations
import time
from loguru import logger

try:
    from langchain_community.tools import DuckDuckGoSearchRun
    _search = DuckDuckGoSearchRun(max_results=5)

    def web_search(query: str) -> str:
        query = query.strip()[:500]
        if not query:
            return "Empty query."
        try:
            time.sleep(0.5)  # polite rate limit
            result = _search.run(query)
            return result or "No results."
        except Exception as e:
            logger.warning(f"Search failed for {query!r}: {e}")
            return f"Search unavailable: {e}"

except ImportError:
    def web_search(query: str) -> str:
        return f"[Search unavailable] Would search: {query}"


def batch_search(queries: list[str]) -> dict[str, str]:
    """Run multiple searches, return {query: result}."""
    results = {}
    for q in queries[:6]:  # cap to 6
        logger.info(f"[search] {q!r}")
        results[q] = web_search(q)
    return results


def format_search_results(results: dict[str, str]) -> str:
    """Format batch results into a readable block."""
    parts = []
    for i, (q, r) in enumerate(results.items(), 1):
        parts.append(f"### Search {i}: {q}\n{r}")
    return "\n\n".join(parts)
