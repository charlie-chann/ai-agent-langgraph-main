# api.py — FastAPI for project_03_multi_agent
import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import run, run_stream
from config import SCENARIO_MARKET_RESEARCH

app = FastAPI(title="Multi-Agent Collaboration API", version="1.0")


class TaskRequest(BaseModel):
    task: str
    scenario: str = SCENARIO_MARKET_RESEARCH


@app.post("/run")
async def run_task(req: TaskRequest):
    result = run(req.task, req.scenario)
    return {
        "final_output": result["final_output"],
        "summary": result["summary"],
        "critique": result["critique"],
        "agent_log": result["agent_log"],
        "total_latency_ms": result["total_latency_ms"],
    }


@app.post("/run/stream")
async def run_task_stream(req: TaskRequest):
    def _gen():
        for event in run_stream(req.task, req.scenario):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/scenarios")
def list_scenarios():
    return [
        {"id": "market_research", "label": "Market Research Report"},
        {"id": "social_media", "label": "Social Media Content"},
    ]


@app.get("/health")
def health():
    return {"status": "ok"}
