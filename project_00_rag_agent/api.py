"""
api.py — FastAPI 生产级 HTTP 接口层（project_00_rag_agent）

【端点一览】
  POST /auth/token                          — JWT 登录
  POST /conversations                       — 创建会话
  GET  /conversations                       — 列出当前用户会话
  GET  /conversations/{id}/messages         — 获取会话消息
  POST /conversations/{id}/chat             — 会话内同步问答（推荐）
  POST /conversations/{id}/chat/stream      — 会话内流式问答
  POST /chat                                — 兼容入口（可自动创建 conversation_id）
  POST /hitl/resume                         — HITL 续跑
  POST /ingest                              — 文档摄入
  GET  /health /ready /stats /metrics
"""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from agent import ask, ask_stream, get_stats, resume_hitl, startup
from core.exceptions import RAGError
from core.compression import dict_history_to_messages
from middleware.auth import TokenPayload, authenticate_user, create_access_token, require_permission
from middleware.rate_limit import rate_limit_middleware
from middleware.request_context import get_request_id, new_request_id
from observability.metrics import inc, snapshot
from storage.conversations import get_conversation_store, messages_as_chat_history
from tools.ingest import ingest_files, sanitize_filename, validate_upload
from core.circuit_breaker import llm_breaker, embed_breaker
from tools.retriever import get_vectorstore


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup()
    from graph.checkpointer import get_checkpointer
    get_checkpointer()
    get_conversation_store().setup()
    yield


app = FastAPI(title="Production RAG Agent API", version="2.1.0", lifespan=lifespan)
app.middleware("http")(rate_limit_middleware)


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str
    password: str


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class ChatRequest(BaseModel):
    """
    聊天请求。生产推荐 POST /conversations/{id}/chat，仅传 message。

    conversation_id 为空时自动创建新会话；chat_history 已废弃（由服务端从 DB 加载）。
    """
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    chat_history: List[dict] = Field(default_factory=list, deprecated=True)
    thread_id: Optional[str] = None
    hitl_approved: bool = False
    use_cache: bool = True


class ConversationChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    hitl_approved: bool = False
    use_cache: bool = True


class HITLResumeRequest(BaseModel):
    thread_id: str
    approved: bool = True


class IngestResponse(BaseModel):
    files_loaded: int
    chunks_created: int
    documents_indexed: int = 0
    kg_triples: int = 0
    error_count: int = 0


# ── 会话辅助 ──────────────────────────────────────────────────────────────────

def _ensure_conversation(user: TokenPayload, conversation_id: Optional[str]) -> str:
    store = get_conversation_store()
    if conversation_id:
        conv = store.get_conversation(conversation_id, user.sub)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation_id
    conv = store.create_conversation(user.sub)
    return conv["conversation_id"]


def _load_history_from_store(conversation_id: str) -> list:
    raw = get_conversation_store().list_messages(conversation_id)
    return dict_history_to_messages(messages_as_chat_history(raw))


def _run_chat(
    *,
    user: TokenPayload,
    conversation_id: str,
    message: str,
    hitl_approved: bool,
    use_cache: bool,
) -> dict:
    store = get_conversation_store()
    history = _load_history_from_store(conversation_id)
    rid = new_request_id()
    inc("requests_total")

    result = ask(
        message,
        history,
        user_roles=[user.role, "public"],
        thread_id=conversation_id,
        conversation_id=conversation_id,
        hitl_approved=hitl_approved,
        use_cache=use_cache,
    )

    store.append_message(conversation_id, "user", message)
    assistant_meta = {
        k: result.get(k)
        for k in ("sources", "latency_ms", "grade", "request_id", "hitl_pending", "cached")
        if result.get(k) is not None
    }
    store.append_message(conversation_id, "assistant", result.get("answer", ""), metadata=assistant_meta)

    # 首条用户消息用作会话标题
    if len(history) == 0:
        title = message.strip().replace("\n", " ")[:80]
        store.touch_conversation(conversation_id, title=title or "New chat")

    if result.get("cached"):
        inc("cache_hits")
    if result.get("hitl_pending"):
        inc("hitl_pending")

    result["role"] = user.role
    result["conversation_id"] = conversation_id
    result["thread_id"] = conversation_id
    return result


# ── 全局异常处理 ──────────────────────────────────────────────────────────────

@app.exception_handler(RAGError)
async def rag_error_handler(_, exc: RAGError):
    inc("errors_total")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "request_id": get_request_id()},
    )


# ── 认证 ──────────────────────────────────────────────────────────────────────

@app.post("/auth/token")
async def login(req: TokenRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ── 会话管理 ──────────────────────────────────────────────────────────────────

@app.post("/conversations")
async def create_conversation(
    req: CreateConversationRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """创建新会话，返回 conversation_id（后续 chat 只需传此 ID + message）。"""
    conv = get_conversation_store().create_conversation(user.sub, title=req.title)
    return conv


@app.get("/conversations")
async def list_conversations(
    user: TokenPayload = Depends(require_permission("chat")),
    limit: int = 50,
):
    return {"conversations": get_conversation_store().list_conversations(user.sub, limit=limit)}


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: TokenPayload = Depends(require_permission("chat")),
):
    store = get_conversation_store()
    if not store.get_conversation(conversation_id, user.sub):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation_id": conversation_id,
        "messages": store.list_messages(conversation_id),
    }


# ── 聊天 ──────────────────────────────────────────────────────────────────────

@app.post("/conversations/{conversation_id}/chat")
async def conversation_chat(
    conversation_id: str,
    req: ConversationChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """生产推荐：服务端从 DB 加载 chat_history，客户端只发 message。"""
    _ensure_conversation(user, conversation_id)
    return _run_chat(
        user=user,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )


@app.post("/conversations/{conversation_id}/chat/stream")
async def conversation_chat_stream(
    conversation_id: str,
    req: ConversationChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    _ensure_conversation(user, conversation_id)
    store = get_conversation_store()
    history = _load_history_from_store(conversation_id)
    new_request_id()
    inc("requests_total")
    store.append_message(conversation_id, "user", req.message)

    def _gen():
        full_answer = ""
        meta: dict = {}
        for token in ask_stream(
            req.message,
            history,
            user_roles=[user.role, "public"],
            conversation_id=conversation_id,
        ):
            if token.startswith("\n\n__META__"):
                meta = json.loads(token.replace("\n\n__META__", ""))
                yield f"data: {json.dumps({**meta, 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            else:
                full_answer += token
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        assistant_meta = {k: meta.get(k) for k in ("sources", "latency_ms", "grade", "request_id") if meta.get(k)}
        store.append_message(conversation_id, "assistant", full_answer, metadata=assistant_meta)
        if len(history) == 0:
            title = req.message.strip().replace("\n", " ")[:80]
            store.touch_conversation(conversation_id, title=title or "New chat")
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/chat")
async def chat(
    req: ChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """
    兼容入口：未传 conversation_id 时自动创建会话。
    chat_history 字段已废弃，历史一律从服务端 DB 读取。
    """
    if req.chat_history:
        logger.warning("chat_history in request body is deprecated; using server-side conversation store")
    conversation_id = _ensure_conversation(user, req.conversation_id)
    return _run_chat(
        user=user,
        conversation_id=conversation_id,
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    conversation_id = _ensure_conversation(user, req.conversation_id)
    fake = ConversationChatRequest(
        message=req.message,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )
    return await conversation_chat_stream(conversation_id, fake, user)


@app.post("/hitl/resume")
async def hitl_resume(
    req: HITLResumeRequest,
    user: TokenPayload = Depends(require_permission("hitl_approve")),
):
    result = resume_hitl(req.thread_id, approved=req.approved)
    if req.approved and result.get("answer"):
        store = get_conversation_store()
        conv = store.get_conversation(req.thread_id, user.sub)
        if conv:
            store.append_message(
                req.thread_id,
                "assistant",
                result["answer"],
                metadata={"hitl_resumed": True, "request_id": result.get("request_id")},
            )
    return result


# ── 文档摄入 ──────────────────────────────────────────────────────────────────

@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: List[UploadFile] = File(...),
    user: TokenPayload = Depends(require_permission("ingest")),
):
    tmp_dir = Path("/tmp/rag_uploads_v2")
    tmp_dir.mkdir(exist_ok=True)
    saved = []
    for f in files:
        content = await f.read()
        validate_upload(f.filename or "upload.txt", len(content))
        safe_name = sanitize_filename(f.filename or "upload.txt")
        dest = tmp_dir / safe_name
        dest.write_bytes(content)
        saved.append(dest)

    result = ingest_files(saved, acl_roles=[user.role, "public"])
    from middleware.cache import cache_delete_prefix
    cache_delete_prefix("rag:ask:")
    return IngestResponse(
        files_loaded=result.get("files_loaded", 0),
        chunks_created=result.get("chunks_created", 0),
        documents_indexed=result.get("documents_indexed", 0),
        kg_triples=result.get("kg_triples", 0),
        error_count=result.get("error_count", 0),
    )


# ── 健康检查与可观测性 ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "request_id": get_request_id()}


@app.get("/ready")
def ready():
    checks = {
        "chroma": False,
        "llm_circuit": not llm_breaker.is_open(),
        "embed_circuit": not embed_breaker.is_open(),
        "conversations": False,
    }
    try:
        get_vectorstore()
        checks["chroma"] = True
    except Exception as e:
        checks["chroma_error"] = str(e)
    try:
        store = get_conversation_store()
        checks["conversations"] = True
        checks["conversations_backend"] = store.backend_name()
    except Exception as e:
        checks["conversations_error"] = str(e)
    status = "ready" if all(v for k, v in checks.items() if not k.endswith("_error") and k != "conversations_backend") else "degraded"
    code = 200 if status == "ready" else 503
    return JSONResponse(status_code=code, content={"status": status, "checks": checks})


@app.get("/stats")
def stats(user: TokenPayload = Depends(require_permission("health"))):
    return get_stats()


@app.get("/metrics")
def metrics(user: TokenPayload = Depends(require_permission("metrics"))):
    return snapshot()
