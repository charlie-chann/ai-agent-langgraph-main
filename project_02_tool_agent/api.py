"""
api.py — Project 02 FastAPI REST 接口

【职责】
1. 暴露 /chat、/chat/stream 等 HTTP 端点，供外部系统调用 Agent
2. 提供带记忆与无记忆两套聊天 API
3. 提供 /memory 记忆管理、/tools 工具列表、/health 健康检查

【设计原因】
1. UI（Streamlit）与 API 分离：同一套 agent.py 逻辑，多种接入方式
2. SSE（Server-Sent Events）流式输出：前端可实时展示 token 与工具调用
3. Pydantic 请求体：自动校验参数、生成 OpenAPI 文档
"""
import json
from typing import List, Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import (
    run, run_stream,
    run_with_memory, run_stream_with_memory,
    get_memory_stats, clear_memory,
    get_stats as get_agent_stats,
)

app = FastAPI(title="Multi-Tool ReAct Agent API", version="2.1")


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """聊天请求体。"""
    message: str                                    # 用户消息
    chat_history: Optional[List[dict]] = None       # 可选历史；memory 模式下可带 session_id


class MemoryRequest(BaseModel):
    """记忆相关请求（预留扩展）。"""
    session_id: str = "default"


# ── 无记忆聊天端点 ────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """单次问答，不保留上下文，每次请求独立。"""
    result = run(req.message)
    return result


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式问答，无记忆。"""
    def _gen():
        for event in run_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── 带记忆聊天端点 ────────────────────────────────────────────────────────────

@app.post("/chat/memory")
async def chat_memory(req: ChatRequest):
    """
    带会话记忆的聊天。

    session_id 从 chat_history[0].session_id 读取，缺省为 "default"。
    同一 session_id 的多轮请求会共享 MemoryStore 中的历史。
    """
    session_id = req.chat_history[0].get("session_id", "default") if req.chat_history else "default"
    result = run_with_memory(req.message, session_id=session_id)
    return result


@app.post("/chat/memory/stream")
async def chat_memory_stream(req: ChatRequest):
    """SSE 流式 + 记忆。"""
    session_id = req.chat_history[0].get("session_id", "default") if req.chat_history else "default"

    def _gen():
        for event in run_stream_with_memory(req.message, session_id=session_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── 记忆管理端点 ──────────────────────────────────────────────────────────────

@app.get("/memory/{session_id}")
def get_memory(session_id: str):
    """查询指定 session 的完整对话历史。"""
    return get_memory_stats(session_id)


@app.get("/memory")
def list_sessions():
    """列出所有 session 及消息数量、最后更新时间。"""
    stats = get_memory_stats()
    return {
        "total_sessions": stats["total_sessions"],
        "sessions": [
            {
                "session_id": s["session_id"],
                "message_count": s["message_count"],
                "last_updated": s["last_updated"],
            }
            for s in stats.get("sessions", [])
        ]
    }


@app.delete("/memory/{session_id}")
def delete_memory(session_id: str):
    """清空指定 session 的记忆。"""
    return clear_memory(session_id)


@app.delete("/memory")
def delete_all_memory():
    """清空全部 session 记忆。"""
    return clear_memory()


# ── 系统端点 ──────────────────────────────────────────────────────────────────

@app.get("/tools")
def list_tools():
    """返回所有可用工具的名称与 description（即 @tool docstring）。"""
    from agent import ALL_TOOLS
    return [{"name": t.name, "description": t.description} for t in ALL_TOOLS]


@app.get("/stats")
def stats():
    """Agent 运行时统计信息。"""
    return get_agent_stats()


@app.get("/health")
def health():
    """健康检查，负载均衡 / K8s probe 使用。"""
    return {"status": "ok", "version": "2.1"}
