# agent.py — Finance / Compliance Analysis Agent
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from langchain_community.llms import Ollama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from loguru import logger

from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE, AGENT_MAX_ITERATIONS
from prompts.finance_prompts import FINANCE_REACT_TEMPLATE
from tools.market_data import get_stock_quote, get_financials, get_price_history, compare_stocks
from tools.news_tool import get_financial_news, get_sector_news
from tools.analysis_tool import calculate_dcf, analyse_fundamentals, calculate_portfolio_metrics
from tools.compliance_tool import check_position_compliance, screen_portfolio_compliance, get_compliance_rules
from tools.report_tool import save_report, list_reports, read_report

# ── All tools ─────────────────────────────────────────────────────────────────
ALL_TOOLS = [
    # Market data
    get_stock_quote,
    get_financials,
    get_price_history,
    compare_stocks,
    # News
    get_financial_news,
    get_sector_news,
    # Analysis
    calculate_dcf,
    analyse_fundamentals,
    calculate_portfolio_metrics,
    # Compliance
    check_position_compliance,
    screen_portfolio_compliance,
    get_compliance_rules,
    # Reports
    save_report,
    list_reports,
    read_report,
]

_TOOL_NAMES = ", ".join(t.name for t in ALL_TOOLS)
_TOOL_DESCS = "\n".join(f"{t.name}: {t.description}" for t in ALL_TOOLS)


def build_agent(model: str | None = None) -> AgentExecutor:
    """Build and return the finance ReAct AgentExecutor."""
    llm = Ollama(
        model=model or DEFAULT_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
    )
    prompt = PromptTemplate.from_template(
        FINANCE_REACT_TEMPLATE.format(tool_names=_TOOL_NAMES, tools=_TOOL_DESCS)
    )
    agent = create_react_agent(llm, ALL_TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=ALL_TOOLS,
        verbose=True,
        max_iterations=AGENT_MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def run_agent(task: str, model: str | None = None) -> dict:
    """Run the finance agent on a task and return result dict."""
    executor = build_agent(model)
    logger.info(f"[finance_agent] task={task!r}")
    result = executor.invoke({"input": task})
    return {
        "output": result.get("output", ""),
        "steps": [
            {"tool": a.tool, "input": a.tool_input, "output": str(o)[:500]}
            for a, o in result.get("intermediate_steps", [])
        ],
    }
