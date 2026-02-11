"""ReAct Agent 图：LLM + 注册工具循环。"""
from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from app.infrastructure.providers.factory import get_chat_model
from app.tools.registry import ALL_TOOLS


def build_graph(*, with_checkpointer: bool = True):
    """构建 ReAct 图（工具来自 app.tools.registry.ALL_TOOLS）。"""
    # create_react_agent 返回已编译图；checkpointer 由 react 模式按需扩展
    return create_react_agent(
        model=get_chat_model(role="generate"),
        tools=ALL_TOOLS,
    )
