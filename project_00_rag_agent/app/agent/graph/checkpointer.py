"""
graph/checkpointer.py — LangGraph Checkpointer 工厂

【职责】
按配置创建 Postgres 或 Memory checkpointer，供 HITL 断点续跑与多轮 thread 状态持久化。

【设计原因】
1. HITL 依赖 checkpointer：interrupt_before 暂停后必须把 state 写入存储，恢复 invoke 才能读到 hitl_approved
2. Postgres 优先、Memory 兜底：生产用 DATABASE_URL 持久化；开发/单测无 DB 时自动降级 MemorySaver
3. 单例 get_checkpointer：与 get_graph 一致，避免重复 setup 连接池
4. reset_checkpointer：测试隔离时清空单例，下次 get 重新按当前 settings 选型
"""
from __future__ import annotations

from loguru import logger

from config import settings

_checkpointer = None  # 全局 checkpointer 单例


def get_checkpointer():
    """
    获取 LangGraph checkpointer 实例（懒加载单例）。

    选型逻辑：
    - checkpointer_backend=postgres 且 database_url 可用 → PostgresSaver（需 cp.setup()）
    - 否则 → MemorySaver（进程内，重启丢失）
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    backend = settings.checkpointer_backend
    if backend == "postgres" and settings.database_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            cp = PostgresSaver.from_conn_string(settings.database_url)
            cp.setup()  # 确保 checkpoint 表已创建
            _checkpointer = cp
            logger.info("Postgres checkpointer initialized")
            return _checkpointer
        except Exception as e:
            # Postgres 不可用时不阻断启动，降级到内存
            logger.warning(f"Postgres checkpointer unavailable, using memory: {e}")

    from langgraph.checkpoint.memory import MemorySaver

    _checkpointer = MemorySaver()
    logger.info("Memory checkpointer initialized")
    return _checkpointer


def reset_checkpointer():
    """清空 checkpointer 单例，配合 reset_graph 在测试中强制重建。"""
    global _checkpointer
    _checkpointer = None
