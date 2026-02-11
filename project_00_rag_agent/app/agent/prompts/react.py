"""ReAct Agent 系统提示（可选自定义；默认使用 create_react_agent 内置 prompt）。"""
from __future__ import annotations

REACT_SYSTEM = """You are a helpful enterprise assistant with access to tools.
Use tools when you need factual or up-to-date information from the knowledge base.
Answer clearly in the user's language."""
