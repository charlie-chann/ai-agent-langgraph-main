# api.py — Browser Agent FastAPI service with SSE streaming
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from loguru import logger
import uvicorn

from config import API_HOST, API_PORT
from tools.task_parser import sanitize_instruction

app = FastAPI(
    title="Browser Automation Agent API",
    description="浏览器自动化 Agent REST + SSE 接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    instruction: str
    max_steps: int = 10

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        return sanitize_instruction(v)

    @field_validator("max_steps")
    @classmethod
    def validate_max_steps(cls, v: int) -> int:
        return max(1, min(v, 20))


class TaskResponse(BaseModel):
    final_report: str
    pages_visited: list[str]
    step_count: int
    total_latency_ms: float


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "browser-agent"}


@app.post("/task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    """Run a browser task synchronously and return the final report."""
    try:
        import config
        config.BROWSER_MAX_STEPS = req.max_steps
        from agent import run_browser_task
        result = run_browser_task(req.instruction)
        return TaskResponse(
            final_report=result.get("final_report", ""),
            pages_visited=list(set(result.get("pages_visited", []))),
            step_count=result.get("step_count", 0),
            total_latency_ms=result.get("total_latency_ms", 0.0),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Task execution error: {e}")
        raise HTTPException(status_code=500, detail=f"执行失败: {e}")


@app.post("/task/stream")
async def stream_task(req: TaskRequest):
    """Stream browser task execution as SSE events."""
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            import config
            config.BROWSER_MAX_STEPS = req.max_steps
            from agent import stream_browser_task

            for event in stream_browser_task(req.instruction):
                for node_name, node_state in event.items():
                    data = {
                        "node": node_name,
                        "step": node_state.get("step_count", 0),
                        "final_report": node_state.get("final_report", ""),
                        "pages_visited": node_state.get("pages_visited", []),
                    }
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': f'执行失败: {e}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=False)
