"""
core/exceptions.py — 结构化异常与 HTTP 状态码映射

【职责】
定义 RAG 服务域内统一异常基类 RAGError 及子类（鉴权、限流、超时、503 等），
供 API 层捕获后转换为一致的 JSON 错误响应（code + status_code + message）。

【设计原因】
1. 避免 API 层散落 magic string 与硬编码 HTTP 码
2. 每个子类携带 code（机器可读）与 status_code（REST 语义），便于前端与监控分类
3. detail 可选字段承载调试信息，生产环境可选择性暴露

【与 project_01 差异】
project_01 以通用 Exception 或 LangChain 异常为主；本模块为 project_00 生产 API
（JWT、限流、熔断、超时）提供统一错误契约。
"""
from __future__ import annotations


class RAGError(Exception):
    """
    RAG 服务异常基类。

    子类通过类属性 code、status_code 区分错误类型；实例携带 message 与可选 detail。
    """

    code: str = "RAG_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class AuthError(RAGError):
    """认证失败（未登录、Token 无效或过期）。"""

    code = "AUTH_ERROR"
    status_code = 401


class ForbiddenError(RAGError):
    """已认证但权限不足（RBAC 拒绝）。"""

    code = "FORBIDDEN"
    status_code = 403


class RateLimitError(RAGError):
    """请求频率超过 Redis 限流阈值。"""

    code = "RATE_LIMIT"
    status_code = 429


class TimeoutError(RAGError):
    """外部调用或 run_with_timeout 超过配置时限。"""

    code = "TIMEOUT"
    status_code = 504


class ServiceUnavailableError(RAGError):
    """依赖不可用（如熔断器开路、Provider 宕机）。"""

    code = "SERVICE_UNAVAILABLE"
    status_code = 503


class ValidationError(RAGError):
    """请求参数校验失败。"""

    code = "VALIDATION_ERROR"
    status_code = 400


class NotFoundError(RAGError):
    """资源不存在（如会话 ID 无效）。"""

    code = "NOT_FOUND"
    status_code = 404
