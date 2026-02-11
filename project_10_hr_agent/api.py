# api.py — HR Agent FastAPI service
from __future__ import annotations

import json
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from loguru import logger
import uvicorn

from config import API_HOST, API_PORT

app = FastAPI(
    title="HR Recruitment Agent API",
    description="HR 招聘筛选 Agent REST + SSE 接口",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class ResumeData(BaseModel):
    id: str
    name: str
    skills: list[str]
    years_experience: int = 0
    education: str = "本科"
    job_count: int = 1
    resume_text: str = ""

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()[:100]
        if not v:
            raise ValueError("候选人姓名不能为空")
        return v

    @field_validator("years_experience")
    @classmethod
    def validate_years(cls, v: int) -> int:
        return max(0, min(v, 50))


class JobRequirementData(BaseModel):
    title: str
    required_skills: list[str]
    preferred_skills: list[str] = []
    min_years_exp: int = 0
    preferred_years_exp: int = 3
    min_education: str = "本科"


class ScreeningRequest(BaseModel):
    job: JobRequirementData
    resumes: list[ResumeData]

    @field_validator("resumes")
    @classmethod
    def validate_resumes(cls, v: list) -> list:
        if len(v) > 50:
            raise ValueError("单批次最多50份简历")
        return v


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()[:2000]
        if not v:
            raise ValueError("消息不能为空")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "hr-agent"}


@app.post("/screen")
def screen_resumes(req: ScreeningRequest):
    """Batch screen resumes against job requirements."""
    try:
        from tools.resume_scorer import JobRequirement, batch_score
        job = JobRequirement(
            title=req.job.title,
            required_skills=req.job.required_skills,
            preferred_skills=req.job.preferred_skills,
            min_years_exp=req.job.min_years_exp,
            preferred_years_exp=req.job.preferred_years_exp,
            min_education=req.job.min_education,
        )
        resumes = [r.model_dump() for r in req.resumes]
        results = batch_score(resumes, job)
        return {"results": [r.to_dict() for r in results]}
    except Exception as e:
        logger.exception(f"Screening error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat(req: ChatRequest):
    """Single-turn HR assistant chat."""
    try:
        from agent import run_hr_chat
        response = run_hr_chat(req.message, req.history)
        return {"response": response}
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming HR assistant chat via SSE."""
    async def gen():
        try:
            from agent import stream_hr_chat
            for event in stream_hr_chat(req.message, req.history):
                for node_name, node_state in event.items():
                    if node_name == "hr_agent":
                        msgs = node_state.get("messages", [])
                        if msgs and hasattr(msgs[-1], "content") and msgs[-1].content:
                            import json as _json
                            yield f"data: {_json.dumps({'content': msgs[-1].content}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            import json as _json
            yield f"data: {_json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run("api:app", host=API_HOST, port=API_PORT, reload=False)
