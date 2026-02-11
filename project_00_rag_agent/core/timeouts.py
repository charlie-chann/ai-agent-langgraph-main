"""
core/timeouts.py — 阻塞调用超时包装

【职责】
对无法在调用点设置 timeout 的阻塞 Callable（如同步 LLM SDK）在独立线程中执行，
并在超时后取消 Future、抛出 domain 层 TimeoutError（映射 HTTP 504）。

【设计原因】
1. Python 标准库无统一的「任意阻塞函数超时」API；ThreadPoolExecutor + future.result(timeout) 通用可靠
2. max_workers=1 避免每次调用创建大量线程；with 语句确保池在退出时 shutdown
3. 将 concurrent.futures.TimeoutError 转为 core.exceptions.TimeoutError，API 层统一处理

【与 project_01 差异】
project_01 依赖 Ollama 客户端默认超时；本模块显式包装 embed/rerank 等阻塞路径，
与 config.llm_timeout / embed_timeout 等配置配合。
"""
from __future__ import annotations

import concurrent.futures
from typing import Callable, TypeVar

from loguru import logger

from core.exceptions import TimeoutError as RAGTimeoutError

T = TypeVar("T")


def run_with_timeout(fn: Callable[[], T], timeout: float, *, label: str = "operation") -> T:
    """
    在子线程中执行无参 Callable，限时等待结果。

    Args:
        fn: 无参可调用对象，通常 lambda 闭包捕获实际参数
        timeout: 最大等待秒数
        label: 日志与异常文案中的操作名，便于定位哪一步超时

    Raises:
        RAGTimeoutError: 超过 timeout 未返回时

    Returns:
        fn() 的返回值
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError as exc:
            logger.warning(f"{label} timed out after {timeout}s")
            raise RAGTimeoutError(f"{label} timed out after {timeout}s") from exc
