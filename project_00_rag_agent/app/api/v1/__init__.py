"""v1 路由汇总。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, health, hitl, ingest

router = APIRouter()
router.include_router(health.router)
router.include_router(chat.router)
router.include_router(ingest.router)
router.include_router(hitl.router)
