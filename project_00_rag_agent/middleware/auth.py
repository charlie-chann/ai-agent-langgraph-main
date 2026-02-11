"""
auth.py — JWT 认证与 RBAC 权限控制

【职责】
1. 演示用户登录校验（用户名/密码 → JWT）
2. JWT 签发与解码
3. 基于角色的权限检查（admin / editor / viewer）
4. 提供 FastAPI Depends 依赖：强制鉴权与可选鉴权

【设计原因】
1. 使用 python-jose 处理 JWT，与 FastAPI 生态兼容
2. RBAC 通过 ROLE_PERMISSIONS 字典集中定义，新增权限只需改一处
3. HTTPBearer(auto_error=False) 允许「可选登录」场景（如公开 health 端点）
4. DEMO_USERS_JSON 从 config 读取，便于本地演示而不硬编码账号

【角色权限一览】
  admin  — chat, ingest, delete, hitl_approve, health, metrics
  editor — chat, ingest, health
  viewer — chat, health
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings

# HTTP Bearer 提取器：从 Authorization: Bearer <token> 头中解析凭证
# auto_error=False 表示无 token 时不自动 403，由业务逻辑决定如何处理
security = HTTPBearer(auto_error=False)

# 角色 → 允许的操作集合（RBAC 核心映射表）
ROLE_PERMISSIONS = {
    "admin": {"chat", "ingest", "delete", "hitl_approve", "health", "metrics"},
    "editor": {"chat", "ingest", "health"},
    "viewer": {"chat", "health"},
}


class TokenPayload(BaseModel):
    """JWT 载荷结构：用户标识 sub、角色 role、过期时间 exp（可选）。"""

    sub: str
    role: str
    exp: int | None = None


def _load_demo_users() -> dict[str, tuple[str, str]]:
    """
    解析 DEMO_USERS_JSON 配置 → {username: (password, role)}。

    格式示例：{"admin": "admin123:admin", "viewer": "pass"}
    - 含冒号：password:role
    - 不含冒号：整段视为密码，默认角色 viewer
    """
    raw = json.loads(settings.demo_users_json)
    out: dict[str, tuple[str, str]] = {}
    for user, val in raw.items():
        if ":" in val:
            pwd, role = val.rsplit(":", 1)
            out[user] = (pwd, role)
        else:
            out[user] = (val, "viewer")
    return out


def authenticate_user(username: str, password: str) -> Optional[TokenPayload]:
    """
    校验用户名与密码，成功返回 TokenPayload，失败返回 None。

    用于 /auth/token 登录端点，不抛异常以便上层统一返回 401。
    """
    users = _load_demo_users()
    entry = users.get(username)
    if not entry or entry[0] != password:
        return None
    return TokenPayload(sub=username, role=entry[1])


def create_access_token(payload: TokenPayload) -> str:
    """
    签发 JWT access token。

    过期时间 = 当前 UTC 时间 + jwt_expire_minutes，写入 exp 字段后 HS256 签名。
    """
    data = payload.model_dump()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    data["exp"] = int(expire.timestamp())
    return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenPayload:
    """
    解码并校验 JWT；签名无效或过期时抛出 HTTP 401。
    """
    try:
        data = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return TokenPayload(**data)
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def require_permission(permission: str):
    """
    工厂函数：返回 FastAPI 依赖，要求调用方携带有效 JWT 且角色具备指定权限。

    用法：Depends(require_permission("ingest"))
    - 无 token → 401
    - 角色无权限 → 403
    - 通过 → 返回 TokenPayload 供路由使用
    """

    async def _dep(
        creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    ) -> TokenPayload:
        if creds is None or not creds.credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
        user = decode_token(creds.credentials)
        allowed = ROLE_PERMISSIONS.get(user.role, set())
        if permission not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{user.role}' cannot '{permission}'")
        return user

    return _dep


def optional_user(
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
) -> Optional[TokenPayload]:
    """
    可选鉴权依赖：有合法 token 则返回用户，否则返回 None（不抛异常）。

    适用于「登录用户有额外能力，匿名用户也能访问」的端点。
    """
    if creds is None or not creds.credentials:
        return None
    try:
        return decode_token(creds.credentials)
    except HTTPException:
        return None
