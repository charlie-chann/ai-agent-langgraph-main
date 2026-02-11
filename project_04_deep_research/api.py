# api.py — FastAPI for project_04_deep_research
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import research, research_stream

app = FastAPI(title="Deep Research Agent API", version="1.0")


class ResearchRequest(BaseModel):
    topic: str


@app.post("/research")
async def run_research(req: ResearchRequest):
    result = research(req.topic)
    return {
        "final_report": result["final_report"],
        "research_notes": result["research_notes"],
        "round": result["round"],
        "coverage_score": result["coverage_score"],
        "all_queries": result["all_queries"],
        "total_latency_ms": result["total_latency_ms"],
        "saved_path": result["saved_path"],
    }


@app.post("/research/stream")
async def run_research_stream(req: ResearchRequest):
    def _gen():
        for event in research_stream(req.topic):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/health")
def health():
    return {"status": "ok"}
