"""Agent Tool 注册表测试。"""
from app.tools import ALL_TOOLS, get_all_tools
from app.tools.knowledge import search_knowledge_base


def test_search_knowledge_base_registered():
    tools = get_all_tools()
    assert search_knowledge_base in tools
    assert len(ALL_TOOLS) >= 1
    assert search_knowledge_base.name == "search_knowledge_base"
