# tests/test_agent.py — project_03_multi_agent (Supervisor + ReAct v3)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest


def test_parse_json_from_llm_output():
    """_parse_json should extract JSON embedded in text."""
    from agent import _parse_json

    raw = 'Here is the plan:\n{"goal": "test", "research_questions": ["q1"]}'
    plan = _parse_json(raw, {})
    assert plan["goal"] == "test"
    assert plan["research_questions"] == ["q1"]


def test_rule_based_next_starts_with_planner():
    """Empty state should route to planner first."""
    from agent import _rule_based_next

    state = {"plan": {}, "research": "", "content": "", "critique": {}, "last_agent": ""}
    assert _rule_based_next(state) == "planner"


def test_rule_based_next_after_plan():
    """With plan but no research → researcher."""
    from agent import _rule_based_next

    state = {
        "plan": {"goal": "x"},
        "research": "",
        "content": "",
        "last_agent": "",
    }
    assert _rule_based_next(state) == "researcher"


def test_critic_routing_pass():
    """Score >= CRITIC_PASS_SCORE should route to summarizer."""
    from agent import _route_after_critic
    from config import CRITIC_PASS_SCORE

    state = {
        "critique": {"overall_score": 9, "verdict": "pass"},
        "revision_count": 1,
    }
    assert _route_after_critic(state) == "summarizer"


def test_critic_routing_revise():
    """Score < CRITIC_PASS_SCORE with room to revise should route to writer."""
    from agent import _route_after_critic

    state = {
        "critique": {"overall_score": 4, "verdict": "revise"},
        "revision_count": 0,
    }
    assert _route_after_critic(state) == "writer"


def test_critic_routing_max_revisions():
    """Exceeded MAX_REVISION_LOOPS should always route to summarizer."""
    from agent import _route_after_critic
    from config import MAX_REVISION_LOOPS

    state = {
        "critique": {"overall_score": 2, "verdict": "revise"},
        "revision_count": MAX_REVISION_LOOPS,
    }
    assert _route_after_critic(state) == "summarizer"


def test_validate_next_blocks_writer_without_research():
    """Supervisor cannot skip to writer before research exists."""
    from agent import _validate_next

    state = {"plan": {"goal": "x"}, "research": "", "content": ""}
    assert _validate_next(state, "writer") == "researcher"


def test_multi_search_no_crash():
    """multi_search should return a string (even if search fails)."""
    from tools.search_tool import multi_search
    result = multi_search(["python programming"])
    assert isinstance(result, str)
    assert len(result) > 0


def test_researcher_tools_registered():
    """Researcher ReAct tools should be importable LangChain tools."""
    from tools.search_tool import RESEARCHER_TOOLS
    names = {t.name for t in RESEARCHER_TOOLS}
    assert "web_search_tool" in names
    assert "multi_search_tool" in names


def test_build_graph_compiles():
    """Supervisor graph should compile without error."""
    from agent import build_graph
    g = build_graph()
    assert g is not None


def test_sub_agents_use_create_agent():
    """Sub-agents should be built with langchain.agents.create_agent (no deprecated API)."""
    from agent import reset_agents, _get_sub_agent
    reset_agents()
    agent = _get_sub_agent("planner")
    assert agent is not None
    assert type(agent).__name__ == "CompiledStateGraph"
