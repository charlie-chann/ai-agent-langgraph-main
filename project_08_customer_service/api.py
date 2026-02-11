"""api.py — 客服 Agent FastAPI + SSE 接口（端口 8008）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

app = FastAPI(
    title="客服 Agent API",
    version="1.0.0",
    description="AI 客服全链路系统 REST + SSE 接口",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    model: str | None = None


class KBSearchRequest(BaseModel):
    query: str


class OrderRequest(BaseModel):
    order_id: str


class TicketCreateRequest(BaseModel):
    user_id: str
    title: str
    description: str
    intent: str = "general"
    priority: str = ""


def _sse(data: str) -> str:
    return f"data: {json.dumps({'text': data}, ensure_ascii=False)}\n\n"


async def _stream_chat(message: str, user_id: str, model: str | None) -> AsyncGenerator[str, None]:
    from agent import build_agent, _build_context_prompt, add_to_session
    from tools.sentiment_tool import analyse_sentiment

    # 预检测情感
    sent_raw = analyse_sentiment.invoke(message)
    sent = json.loads(sent_raw)
    yield _sse(f"[情感分析] 负面评分: {sent.get('score', 0):.2f} | 需升级: {sent.get('needs_escalation', False)}\n")
    await asyncio.sleep(0)

    executor = build_agent(model)
    full_input = _build_context_prompt(user_id, message)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, executor.invoke, {"input": full_input})

    steps = result.get("intermediate_steps", [])
    for i, (action, obs) in enumerate(steps, 1):
        yield _sse(f"[工具 {i}: {action.tool}] {str(obs)[:150]}\n")
        await asyncio.sleep(0)

    output = result.get("output", "")
    add_to_session(user_id, "user", message)
    add_to_session(user_id, "assistant", output)

    # 流式输出最终回复
    for word in output.split():
        yield _sse(word + " ")
        await asyncio.sleep(0)
    yield "data: [DONE]\n\n"


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE 流式对话接口"""
    if not req.message.strip():
        raise HTTPException(400, "message 不能为空")
    return StreamingResponse(
        _stream_chat(req.message, req.user_id, req.model),
        media_type="text/event-stream",
    )


@app.post("/chat")
async def chat_invoke(req: ChatRequest):
    """同步对话接口，返回完整结果"""
    if not req.message.strip():
        raise HTTPException(400, "message 不能为空")
    from agent import run_agent
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_agent, req.message, req.user_id, req.model)


@app.post("/kb/search")
async def kb_search(req: KBSearchRequest):
    """搜索知识库"""
    from tools.kb_tool import search_kb
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, search_kb.invoke, req.query)
    return json.loads(raw)


@app.post("/order/status")
async def order_status(req: OrderRequest):
    """查询订单状态"""
    from tools.order_tool import query_order_status
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, query_order_status.invoke, req.order_id)
    return json.loads(raw)


@app.post("/ticket/create")
async def ticket_create(req: TicketCreateRequest):
    """创建工单"""
    from tools.ticket_tool import create_ticket
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, create_ticket.invoke, {
        "user_id": req.user_id, "title": req.title,
        "description": req.description, "intent": req.intent,
        "priority": req.priority,
    })
    return json.loads(raw)


@app.post("/sentiment")
async def sentiment_check(req: KBSearchRequest):
    """分析消息情感"""
    from tools.sentiment_tool import analyse_sentiment
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, analyse_sentiment.invoke, req.query)
    return json.loads(raw)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "customer_service_agent", "port": 8008}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
