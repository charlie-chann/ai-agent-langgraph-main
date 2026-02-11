# api.py — FastAPI for project_02_tool_agent (with memory)
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


# ── Request/Response Models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[dict]] = None


class MemoryRequest(BaseModel):
    session_id: str = "default"


# ── Chat Endpoints (without memory) ────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """Simple chat without memory (each request is independent)."""
    result = run(req.message)
    return result


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat without memory."""
    def _gen():
        for event in run_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── Chat Endpoints (with memory) ───────────────────────────────────────────────

@app.post("/chat/memory")
async def chat_memory(req: ChatRequest):
    """
    Chat WITH automatic conversation memory.
    
    The agent remembers the conversation history within the session.
    Use the same session_id to continue conversations.
    """
    session_id = req.chat_history[0].get("session_id", "default") if req.chat_history else "default"
    result = run_with_memory(req.message, session_id=session_id)
    return result


@app.post("/chat/memory/stream")
async def chat_memory_stream(req: ChatRequest):
    """Streaming chat WITH memory."""
    session_id = req.chat_history[0].get("session_id", "default") if req.chat_history else "default"
    
    def _gen():
        for event in run_stream_with_memory(req.message, session_id=session_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(_gen(), media_type="text/event-stream")


# ── Memory Management Endpoints ───────────────────────────────────────────────

@app.get("/memory/{session_id}")
def get_memory(session_id: str):
    """Get conversation history for a session."""
    return get_memory_stats(session_id)


@app.get("/memory")
def list_sessions():
    """List all memory sessions."""
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
    """Clear memory for a specific session."""
    return clear_memory(session_id)


@app.delete("/memory")
def delete_all_memory():
    """Clear all memory sessions."""
    return clear_memory()


# ── System Endpoints ──────────────────────────────────────────────────────────

@app.get("/tools")
def list_tools():
    """List all available tools."""
    from agent import ALL_TOOLS
    return [{"name": t.name, "description": t.description} for t in ALL_TOOLS]


@app.get("/stats")
def stats():
    """Get agent statistics."""
    return get_agent_stats()


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1"}
