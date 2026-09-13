"""Agent 图工厂：按 mode 返回 rag / react 等已编译图。"""
from __future__ import annotations

from typing import Any, Literal

from app.core.config import settings

AgentMode = Literal["rag", "react"]

_graph_cache: dict[str, Any] = {}


def normalize_agent_mode(mode: str | None) -> str:
    """规范化 agent 模式名；空值时回落到默认配置。"""
    return (mode or settings.default_agent_mode).lower()


def get_graph(agent_mode: str | None = None):
    """懒加载获取指定模式的已编译 LangGraph。"""
    mode = normalize_agent_mode(agent_mode)
    if mode not in _graph_cache:
        if mode == "rag":
            from app.agent.graphs.rag.builder import build_graph

            _graph_cache[mode] = build_graph()
        elif mode == "react":
            from app.agent.graphs.react.builder import build_graph

            _graph_cache[mode] = build_graph()
        else:
            raise ValueError(f"Unknown agent mode: {mode}")
    return _graph_cache[mode]


def reset_graph(agent_mode: str | None = None) -> None:
    """测试或配置变更时清空图缓存。"""
    from app.agent.checkpointer import reset_checkpointer

    if agent_mode:
        _graph_cache.pop(normalize_agent_mode(agent_mode), None)
    else:
        _graph_cache.clear()
    reset_checkpointer()


def supported_modes() -> list[str]:
    """返回当前支持的 agent 模式列表。"""
    return ["rag", "react"]
