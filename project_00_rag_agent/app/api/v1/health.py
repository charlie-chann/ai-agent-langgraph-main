"""健康检查、鉴权登录与运维指标。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.api.deps import TokenPayload, require_permission
from app.core.config import settings
from app.gateway.auth import authenticate_user, create_access_token
from app.gateway.request_context import get_request_id
from app.infrastructure.observability.metrics import snapshot
from app.schemas.common import TokenRequest
from app.services.health_service import get_readiness
from app.services.agent_service import get_stats

router = APIRouter(tags=["health"])


@router.post("/auth/token")
async def login(req: TokenRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@router.get("/health")
def health():
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "request_id": get_request_id(),
    }


@router.get("/ready")
def ready():
    code, body = get_readiness()
    return JSONResponse(status_code=code, content=body)


@router.get("/stats")
def stats(user: TokenPayload = Depends(require_permission("health"))):
    return get_stats()


@router.get("/metrics")
def metrics(user: TokenPayload = Depends(require_permission("metrics"))):
    return snapshot()
