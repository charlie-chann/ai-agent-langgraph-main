"""Project 29 - 个人记忆 Agent FastAPI 服务"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import json
from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import (
    run_remember, run_recall, run_forget, run_update,
    run_list_memories, run_get_stats, stream_chat
)
from config import DEFAULT_MODEL, MEMORY_TYPES, IMPORTANCE_LEVELS

app = FastAPI(
    title="🧠 OpenClaw 个人记忆 Agent API",
    description="持久化个人知识管理与智能记忆召回服务",
    version="1.0.0"
)


class RememberRequest(BaseModel):
    content: str = Field(..., description="要记住的内容")
    memory_type: str = Field("note", description=f"记忆类型: {MEMORY_TYPES}")
    importance: str = Field("medium", description=f"重要程度: {IMPORTANCE_LEVELS}")
    tags: list[str] | None = Field(None, description="标签列表")


class RecallRequest(BaseModel):
    query: str = Field(..., description="搜索关键词")
    memory_type: str | None = Field(None, description="类型过滤")
    importance: str | None = Field(None, description="重要性过滤")
    tags: list[str] | None = Field(None, description="标签过滤")
    max_results: int = Field(10, ge=1, le=50)


class UpdateRequest(BaseModel):
    content: str | None = Field(None, description="新内容")
    importance: str | None = Field(None, description="新重要程度")
    tags: list[str] | None = Field(None, description="新标签")


@app.get("/", summary="健康检查")
async def health():
    stats = run_get_stats()
    return {
        "status": "ok",
        "project": "personal_memory",
        "model": DEFAULT_MODEL,
        "total_memories": stats.get("total", 0)
    }


@app.post("/memory/remember", summary="记录新记忆")
async def remember(req: RememberRequest):
    result = run_remember(
        content=req.content,
        memory_type=req.memory_type,
        importance=req.importance,
        tags=req.tags
    )
    if not result["success"]:
        return {"success": False, "error": result.get("error")}
    m = result["memory"]
    return {
        "success": True,
        "id": result["id"],
        "memory_type": m.memory_type,
        "importance": m.importance,
        "tags": m.tags,
        "created_at": m.created_at,
        "error": None
    }


@app.post("/memory/recall", summary="召回相关记忆")
async def recall(req: RecallRequest):
    result = run_recall(
        query=req.query,
        memory_type=req.memory_type,
        importance=req.importance,
        tags=req.tags,
        max_results=req.max_results
    )
    # Serialize Memory dataclass to dict
    serialized = [
        {
            "id": m.id,
            "content": m.content,
            "memory_type": m.memory_type,
            "importance": m.importance,
            "tags": m.tags,
            "created_at": m.created_at,
            "access_count": m.access_count
        }
        for m in result.get("results", [])
    ]
    return {"success": result["success"], "results": serialized, "count": result["count"]}


@app.delete("/memory/{memory_id}", summary="删除记忆")
async def forget(memory_id: str):
    result = run_forget(memory_id)
    return result


@app.put("/memory/{memory_id}", summary="更新记忆")
async def update(memory_id: str, req: UpdateRequest):
    result = run_update(
        memory_id=memory_id,
        content=req.content,
        importance=req.importance,
        tags=req.tags
    )
    return result


@app.get("/memory/stats", summary="记忆库统计")
async def stats():
    return run_get_stats()


@app.get("/memory/list", summary="列出所有记忆")
async def list_memories(limit: int = Query(50, ge=1, le=500)):
    result = run_list_memories(limit)
    serialized = [
        {"id": m.id, "content": m.content[:100], "memory_type": m.memory_type,
         "importance": m.importance, "tags": m.tags, "created_at": m.created_at}
        for m in result.get("memories", [])
    ]
    return {"memories": serialized, "count": result["count"]}


@app.get("/chat/stream", summary="流式对话 (SSE)")
async def chat_stream(message: str = Query(..., description="用户消息")):
    def event_generator():
        try:
            for chunk in stream_chat(message):
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8029)
