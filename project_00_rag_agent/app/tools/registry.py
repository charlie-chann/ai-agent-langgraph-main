"""Agent Tool 注册表：汇总所有可供 LLM 调用的工具。"""
from __future__ import annotations

from typing import List

from langchain_core.tools import BaseTool

from app.tools.knowledge import search_knowledge_base


def get_all_tools() -> List[BaseTool]:
    """返回当前项目注册的全部 Agent Tools。"""
    return [search_knowledge_base]


ALL_TOOLS: List[BaseTool] = get_all_tools()
