"""api.py — FastAPI + SSE for Code Agent (port 8006)"""
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

app = FastAPI(title="Code Agent API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    task: str
    model: str | None = None


class ExecuteRequest(BaseModel):
    code: str


class ReviewRequest(BaseModel):
    code: str
    language: str = "python"


def _sse(data: str) -> str:
    return f"data: {json.dumps({'text': data})}\n\n"


async def _stream_gen(task: str, model: str | None) -> AsyncGenerator[str, None]:
    from agent import build_agent

    executor = build_agent(model)
    loop = asyncio.get_event_loop()

    def _invoke():
        return executor.invoke({"input": task})

    result = await loop.run_in_executor(None, _invoke)
    output: str = result.get("output", "")
    steps = result.get("intermediate_steps", [])

    # Stream step summaries first
    for i, (action, obs) in enumerate(steps, 1):
        yield _sse(f"[Tool {i}: {action.tool}] {str(obs)[:200]}\n")
        await asyncio.sleep(0)

    # Stream final output word-by-word for visual effect
    words = output.split()
    chunk: list[str] = []
    for word in words:
        chunk.append(word)
        if len(chunk) >= 5:
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
    return StreamingResponse(
        _stream_gen(req.task, req.model),
        media_type="text/event-stream",
    )


@app.post("/agent/invoke")
async def agent_invoke(req: AgentRequest):
    if not req.task.strip():
        raise HTTPException(400, "task is required")
    from agent import run_agent

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, run_agent, req.task, req.model)
    return result


@app.post("/execute")
async def execute_code(req: ExecuteRequest):
    if not req.code.strip():
        raise HTTPException(400, "code is required")
    from tools.code_executor import execute_python

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, execute_python.invoke, req.code)
    return {"output": result}


@app.post("/review")
async def review_code(req: ReviewRequest):
    if not req.code.strip():
        raise HTTPException(400, "code is required")
    from tools.code_reviewer import review_code as _review

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _review.invoke, {"code": req.code, "language": req.language})
    return {"review": result}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "code_agent", "port": 8006}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8006)
