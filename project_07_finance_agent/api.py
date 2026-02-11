"""api.py — FastAPI + SSE for Finance Agent (port 8007)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import asyncio
import json
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

app = FastAPI(
    title="Finance Agent API",
    version="1.0.0",
    description="AI-powered stock research, fundamental analysis, and compliance screening API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    task: str
    model: str | None = None


class QuoteRequest(BaseModel):
    ticker: str


class ComplianceRequest(BaseModel):
    portfolio: list[dict]


class AnalysisRequest(BaseModel):
    metrics: dict


def _sse(data: str) -> str:
    return f"data: {json.dumps({'text': data})}\n\n"


async def _stream_agent(task: str, model: str | None) -> AsyncGenerator[str, None]:
    from agent import build_agent

    executor = build_agent(model)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, executor.invoke, {"input": task})

    steps = result.get("intermediate_steps", [])
    for i, (action, obs) in enumerate(steps, 1):
        yield _sse(f"[Tool {i}/{len(steps)}: {action.tool}] {str(obs)[:200]}\n")
        await asyncio.sleep(0)

    output = result.get("output", "")
    words = output.split()
    chunk: list[str] = []
    for word in words:
        chunk.append(word)
        if len(chunk) >= 6:
            yield _sse(" ".join(chunk) + " ")
            chunk = []
            await asyncio.sleep(0)
    if chunk:
        yield _sse(" ".join(chunk))
    yield "data: [DONE]\n\n"


@app.post("/agent/stream")
async def agent_stream(req: AgentRequest):
    if not req.task.strip():
        raise HTTPException(400, "task is required")
    return StreamingResponse(_stream_agent(req.task, req.model), media_type="text/event-stream")


@app.post("/agent/invoke")
async def agent_invoke(req: AgentRequest):
    if not req.task.strip():
        raise HTTPException(400, "task is required")
    from agent import run_agent
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_agent, req.task, req.model)


@app.post("/quote")
async def quote(req: QuoteRequest):
    if not req.ticker.strip():
        raise HTTPException(400, "ticker is required")
    from tools.market_data import get_stock_quote
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, get_stock_quote.invoke, req.ticker.upper())
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


@app.post("/compliance/screen")
async def compliance_screen(req: ComplianceRequest):
    from tools.compliance_tool import screen_portfolio_compliance
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, screen_portfolio_compliance.invoke, json.dumps(req.portfolio))
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


@app.post("/analysis/fundamentals")
async def analysis(req: AnalysisRequest):
    from tools.analysis_tool import analyse_fundamentals
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, analyse_fundamentals.invoke, json.dumps(req.metrics))
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "finance_agent", "port": 8007}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
