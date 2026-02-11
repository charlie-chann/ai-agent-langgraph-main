# tests/test_agent.py — project_04_deep_research
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import pytest


def test_parse_json_list_valid():
    """_parse_json_list correctly extracts valid JSON arrays."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p04_agent", Path(__file__).parent.parent / "agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod._parse_json_list('["q1", "q2", "q3"]')
    assert result == ["q1", "q2", "q3"]


def test_parse_json_list_markdown():
    """_parse_json_list handles JSON embedded in markdown."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p04_agent2", Path(__file__).parent.parent / "agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    result = mod._parse_json_list('Here are queries:\n["q1", "q2"]')
    assert "q1" in result


def test_routing_sufficient_coverage():
    """High coverage score should route to write_report."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p04_agent3", Path(__file__).parent.parent / "agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    state = {
        "coverage_score": 0.9,
        "round": 2,
        "gap_analysis": {"ready_to_write": True},
    }
    route = mod._should_continue_research(state)
    assert route == "write_report"


def test_routing_low_coverage():
    """Low coverage within max rounds should route to generate_queries."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p04_agent4", Path(__file__).parent.parent / "agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    state = {
        "coverage_score": 0.3,
        "round": 1,
        "gap_analysis": {"ready_to_write": False},
    }
    route = mod._should_continue_research(state)
    assert route == "generate_queries"


def test_routing_max_rounds_forces_write():
    """Reaching MAX_SEARCH_ROUNDS must route to write_report regardless of score."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "p04_agent5", Path(__file__).parent.parent / "agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from config import MAX_SEARCH_ROUNDS
    state = {
        "coverage_score": 0.1,
        "round": MAX_SEARCH_ROUNDS,
        "gap_analysis": {"ready_to_write": False},
    }
    route = mod._should_continue_research(state)
    assert route == "write_report"


def test_report_saver(tmp_path, monkeypatch):
    """report_saver creates a .md file in the output directory."""
    monkeypatch.setenv("REPORT_OUTPUT_DIR", str(tmp_path))
    # Re-import after env var change
    import importlib
    import tools.report_saver as rs
    importlib.reload(rs)

    from tools.report_saver import save_report
    path = save_report("test topic", "# Hello\ncontent")
    assert path.exists()
    assert path.read_text() == "# Hello\ncontent"


def test_batch_search_returns_string():
    """batch_search always returns a dict of strings."""
    from tools.search_tool import batch_search
    result = batch_search(["python language"])
    assert isinstance(result, dict)
    for v in result.values():
        assert isinstance(v, str)
