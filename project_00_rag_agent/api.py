"""
api.py — FastAPI 生产级 HTTP 接口层（project_00_rag_agent）

【职责】
把 RAG Agent 能力暴露为 REST API，供前端、Streamlit UI、其他微服务调用。

【与 app.py 的关系】
- app.py：Streamlit 人机界面，可直连 agent（Local）或调本 API（API 模式）
- api.py：无 UI 的纯接口，面向系统集成与 K8s 部署

【端点一览】
  POST /auth/token      — JWT 登录
  POST /chat            — 同步问答（含 HITL、缓存、ACL）
  POST /chat/stream     — SSE 流式问答
  POST /hitl/resume     — 人工审批后继续 LangGraph 线程
  POST /ingest          — 上传文件并建立索引 + KG
  GET  /health          — 存活探针
  GET  /ready           — 就绪探针（Chroma + 熔断器状态）
  GET  /stats           — Agent 运行统计
  GET  /metrics         — 可观测性指标快照

【中间件与安全】
- rate_limit_middleware：按 IP/用户限流
- require_permission：RBAC 权限校验（chat / ingest / hitl_approve 等）
- lifespan startup：加载向量库、BM25、Checkpointer 等
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

# 确保以项目根目录运行时能正确 import 本地模块
sys.path.insert(0, str(Path(__file__).parent))

from agent import ask, ask_stream, get_stats, resume_hitl, startup
from core.exceptions import RAGError, ValidationError
from core.compression import dict_history_to_messages
from middleware.auth import TokenPayload, authenticate_user, create_access_token, require_permission
from middleware.rate_limit import rate_limit_middleware
from middleware.request_context import get_request_id, new_request_id
from observability.metrics import inc, snapshot
from tools.ingest import ingest_files, sanitize_filename, validate_upload
from core.circuit_breaker import llm_breaker, embed_breaker
from providers.factory import get_embeddings
from tools.retriever import get_vectorstore, rebuild_bm25_from_chroma


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期：启动时初始化 Agent/向量库/BM25，关闭时由框架清理。

    get_checkpointer() 确保 LangGraph 持久化 checkpointer 就绪（HITL 多轮）。
    """
    startup()
    from graph.checkpointer import get_checkpointer
    get_checkpointer()
    yield


app = FastAPI(title="Production RAG Agent API", version="2.0.0", lifespan=lifespan)
app.middleware("http")(rate_limit_middleware)


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    """登录请求：用户名 + 密码（demo 用户见 middleware.auth）。"""
    username: str
    password: str


class ChatRequest(BaseModel):
    """
    聊天请求体。

    message：用户问题
    chat_history：多轮历史（dict 列表，由 compression 转为 LangChain Message）
    thread_id：LangGraph 线程 ID，HITL 续跑时必传
    hitl_approved：是否已获人工批准（敏感操作链）
    use_cache：是否使用问答结果缓存
    """
    message: str = Field(..., min_length=1, max_length=4000)
    chat_history: List[dict] = []
    thread_id: Optional[str] = None
    hitl_approved: bool = False
    use_cache: bool = True


class HITLResumeRequest(BaseModel):
    """人工审批后继续执行：指定 thread_id 与是否批准。"""
    thread_id: str
    approved: bool = True


class IngestResponse(BaseModel):
    """文档摄入结果统计。"""
    files_loaded: int
    chunks_created: int
    documents_indexed: int = 0
    kg_triples: int = 0
    error_count: int = 0


# ── 全局异常处理 ──────────────────────────────────────────────────────────────

@app.exception_handler(RAGError)
async def rag_error_handler(_, exc: RAGError):
    """
    统一 RAG 业务异常 → JSON 响应，携带 error code、message、request_id。
    """
    inc("errors_total")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "request_id": get_request_id()},
    )


# ── 认证 ──────────────────────────────────────────────────────────────────────

@app.post("/auth/token")
async def login(req: TokenRequest):
    """
    用户名密码校验通过后签发 JWT access_token。

    返回 role 字段供前端展示当前 RBAC 角色。
    """
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return {"access_token": token, "token_type": "bearer", "role": user.role}


# ── 聊天 ──────────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(
    req: ChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """
    非流式聊天：等待完整 LangGraph 执行完毕，一次返回 JSON。

    user_roles 传入 [用户角色, "public"]，供 retriever ACL 过滤。
    统计 requests_total、cache_hits、hitl_pending 等指标。
    """
    rid = new_request_id()
    inc("requests_total")
    history = dict_history_to_messages(req.chat_history)
    result = ask(
        req.message,
        history,
        user_roles=[user.role, "public"],
        thread_id=req.thread_id or rid,
        hitl_approved=req.hitl_approved,
        use_cache=req.use_cache,
    )
    if result.get("cached"):
        inc("cache_hits")
    if result.get("hitl_pending"):
        inc("hitl_pending")
    result["role"] = user.role
    return result


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user: TokenPayload = Depends(require_permission("chat")),
):
    """
    SSE 流式聊天。

    每个 event 格式：
      data: {"token": "..."}   — 正文 token
      data: {...metadata...}   — agent 的 __META__（来源、耗时等）
      data: [DONE]             — 结束标记
    """
    new_request_id()
    inc("requests_total")
    history = dict_history_to_messages(req.chat_history)

    def _gen():
        for token in ask_stream(req.message, history, user_roles=[user.role, "public"]):
            if token.startswith("\n\n__META__"):
                meta = token.replace("\n\n__META__", "")
                yield f"data: {meta}\n\n"
            else:
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/hitl/resume")
async def hitl_resume(
    req: HITLResumeRequest,
    user: TokenPayload = Depends(require_permission("hitl_approve")),
):
    """
    Human-in-the-Loop：管理员批准或拒绝挂起的 LangGraph 线程。
    """
    return resume_hitl(req.thread_id, approved=req.approved)


# ── 文档摄入 ──────────────────────────────────────────────────────────────────

@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    files: List[UploadFile] = File(...),
    user: TokenPayload = Depends(require_permission("ingest")),
):
    """
    上传一个或多个文件，执行 validate → save → ingest_files。

    文件先存 /tmp/rag_uploads_v2/，再交给 ingest 流水线。
    成功后清除 rag:ask: 前缀缓存，避免旧答案与新索引不一致。
    acl_roles 含用户角色与 public，与 JWT 权限模型一致。
    """
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
    """存活探针：进程正常即返回 ok，不检查依赖。"""
    return {"status": "ok", "request_id": get_request_id()}


@app.get("/ready")
def ready():
    """
    就绪探针：检查 Chroma 可连接、LLM/Embedding 熔断器未打开。

    degraded 时返回 503，供 K8s 决定是否接流量。
    """
    checks = {"chroma": False, "llm_circuit": not llm_breaker.is_open(), "embed_circuit": not embed_breaker.is_open()}
    try:
        get_vectorstore()
        checks["chroma"] = True
    except Exception as e:
        checks["chroma_error"] = str(e)
    status = "ready" if all(v for k, v in checks.items() if not k.endswith("_error")) else "degraded"
    code = 200 if status == "ready" else 503
    return JSONResponse(status_code=code, content={"status": status, "checks": checks})


@app.get("/stats")
def stats(user: TokenPayload = Depends(require_permission("health"))):
    """Agent 内部统计（需 health 权限）。"""
    return get_stats()


@app.get("/metrics")
def metrics(user: TokenPayload = Depends(require_permission("metrics"))):
    """Prometheus 风格或自定义指标快照（需 metrics 权限）。"""
    return snapshot()
