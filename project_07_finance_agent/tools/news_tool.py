# tools/news_tool.py — Financial news retrieval via DuckDuckGo
"""Fetch financial news without requiring any API key."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from langchain_core.tools import tool
from loguru import logger

try:
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
    _DDG_AVAILABLE = True
except ImportError:
    _DDG_AVAILABLE = False

from config import MAX_NEWS_RESULTS


@tool
def get_financial_news(query: str) -> str:
    """Fetch recent financial news for a company or topic.
    Input: search query (e.g. 'Apple earnings 2024', 'Federal Reserve rate decision').
    Returns: list of recent news headlines and summaries.
    """
    if not _DDG_AVAILABLE:
        return "DuckDuckGo search not available. Install langchain-community."
    query = query.strip()
    if not query:
        return "Error: empty query"
    try:
        search = DuckDuckGoSearchAPIWrapper(max_results=MAX_NEWS_RESULTS)
        # Narrow to financial/business news
        results = search.results(f"{query} site:reuters.com OR site:bloomberg.com OR site:wsj.com OR {query} financial news", MAX_NEWS_RESULTS)
        if not results:
            results = search.results(query, MAX_NEWS_RESULTS)

        items = []
        for r in results:
            items.append({
                "title": r.get("title", ""),
                "snippet": r.get("snippet", "")[:300],
                "link": r.get("link", ""),
            })
        logger.info(f"[news] query={query!r} results={len(items)}")
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[news] {e}")
        return f"Error fetching news: {e}"


@tool
def get_sector_news(sector: str) -> str:
    """Fetch recent news for a market sector or industry.
    Input: sector name (e.g. 'technology', 'healthcare', 'energy', 'financial services').
    Returns: recent sector news and trends.
    """
    if not _DDG_AVAILABLE:
        return "DuckDuckGo search not available"
    sector = sector.strip()
    if not sector:
        return "Error: empty sector"
    try:
        search = DuckDuckGoSearchAPIWrapper(max_results=MAX_NEWS_RESULTS)
        results = search.results(f"{sector} sector market news outlook 2024 2025", MAX_NEWS_RESULTS)
        items = [
            {
                "title": r.get("title", ""),
                "snippet": r.get("snippet", "")[:300],
            }
            for r in results
        ]
        return json.dumps({"sector": sector, "news": items}, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"
