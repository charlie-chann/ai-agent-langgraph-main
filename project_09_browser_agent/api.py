# api.py — Browser Agent FastAPI HTTP 服务
#
# 【职责】对外暴露 REST + SSE 接口，供前端或其他服务调用浏览器 Agent。
# 【接口】
#   GET  /health       → 健康检查
#   POST /task         → 同步执行（内部 graph.invoke）
#   POST /task/stream  → SSE 流式执行（内部 graph.stream）
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


# ── 请求/响应数据模型 ─────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    """任务请求体：自然语言指令 + 最大 ReAct 步数。"""
    instruction: str
    max_steps: int = 10

    @field_validator("instruction")
    @classmethod
    def validate_instruction(cls, v: str) -> str:
        """校验并清洗指令，拦截注入攻击。"""
        return sanitize_instruction(v)

    @field_validator("max_steps")
    @classmethod
    def validate_max_steps(cls, v: int) -> int:
        """限制步数在 1~20 之间。"""
        return max(1, min(v, 20))


class TaskResponse(BaseModel):
    """同步任务完成后的响应结构。"""
    final_report: str       # Markdown 报告
    pages_visited: list[str]  # 访问过的 URL 列表
    step_count: int         # 实际执行步数
    total_latency_ms: float # 总耗时（毫秒）


# ── API 端点 ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """健康检查，供负载均衡 / K8s 探针使用。"""
    return {"status": "ok", "service": "browser-agent"}


@app.post("/task", response_model=TaskResponse)
def run_task(req: TaskRequest):
    """同步执行任务：等待 graph.invoke 跑完后一次性返回报告。"""
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
    """SSE 流式执行：每完成一个图节点推送一次事件，前端可实时显示进度。"""
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
