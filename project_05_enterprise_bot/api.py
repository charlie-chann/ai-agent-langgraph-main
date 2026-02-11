# api.py — FastAPI for project_05_enterprise_bot
import json
from typing import List

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import chat, get_history, clear_history
from tools.rbac import get_user_role, get_allowed_tools

app = FastAPI(title="Enterprise Bot API", version="1.0")


class ChatRequest(BaseModel):
    message: str
    username: str = "emp_charlie"


class ClearRequest(BaseModel):
    username: str


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Non-streaming chat endpoint with RBAC."""
    result = chat(req.username, req.message)
    return result


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE streaming endpoint (token-level streaming version)."""
    from langchain_community.chat_models import ChatOllama
    from langchain.agents import AgentExecutor, create_react_agent
    from config import OLLAMA_BASE_URL, DEFAULT_MODEL, TEMPERATURE
    from prompts.bot_prompts import bot_prompt
    from tools.rbac import get_allowed_tools

    user_tools_names = get_allowed_tools(req.username)
    from agent import ALL_TOOLS
    user_tools = [t for t in ALL_TOOLS if t.name in user_tools_names]
    role = get_user_role(req.username)
    history = get_history(req.username)

    tokens: list[str] = []

    def _gen():
        result = chat(req.username, req.message)
        # Emit answer token by token for demo purposes
        for word in result["answer"].split(" "):
            payload = json.dumps({"type": "token", "content": word + " "})
            yield f"data: {payload}\n\n"
        meta = json.dumps({
            "type": "done",
            "steps": result.get("steps", []),
            "latency_ms": result.get("latency_ms", 0),
            "role": result.get("role", ""),
        })
        yield f"data: {meta}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/history/{username}")
async def get_chat_history(username: str):
    history = get_history(username)
    return {"username": username, "messages": len(history)}


@app.post("/history/clear")
async def clear_chat_history(req: ClearRequest):
    clear_history(req.username)
    return {"cleared": True, "username": req.username}


@app.get("/user/{username}/permissions")
async def user_permissions(username: str):
    return {
        "username": username,
        "role": get_user_role(username),
        "allowed_tools": get_allowed_tools(username),
    }


@app.get("/health")
def health():
    return {"status": "ok"}
