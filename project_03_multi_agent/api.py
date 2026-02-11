"""
api.py — Multi-Agent 协作系统 FastAPI 服务

【职责】
1. 暴露 REST 端点：同步运行 /run、SSE 流式 /run/stream、场景列表 /scenarios、健康检查 /health
2. 将 agent.run / agent.run_stream 封装为 HTTP 请求-响应与 Server-Sent Events
3. 定义 TaskRequest 请求体模型，校验 task 与 scenario 参数

【设计原因】
1. FastAPI + Pydantic：自动 OpenAPI 文档与请求校验，便于前端/脚本集成
2. /run/stream 使用 SSE（text/event-stream）：与 Streamlit UI 相同的 node_complete 事件协议
3. 同步 /run 仅返回展示所需字段：不暴露完整内部 state，减小响应体积
4. /scenarios 静态列表：UI 与 API 客户端可动态拉取场景，无需硬编码
"""
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
    """
    POST /run 与 /run/stream 的请求体。

    字段:
        task: 用户任务描述（必填）
        scenario: 业务场景 id，默认 market_research
    """
    task: str
    scenario: str = SCENARIO_MARKET_RESEARCH


@app.post("/run")
async def run_task(req: TaskRequest):
    """
    同步执行多 Agent 流水线，一次性返回完整结果。

    参数:
        req: TaskRequest（task + scenario）

    返回:
        final_output、summary、critique、agent_log、total_latency_ms
    """
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
    """
    SSE 流式执行：每完成一个 Agent 节点推送一条 JSON 事件。

    参数:
        req: TaskRequest

    返回:
        StreamingResponse，media_type=text/event-stream
        每条 data 为 JSON；结束时发送 data: [DONE]
    """
    def _gen():
        for event in run_stream(req.task, req.scenario):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/scenarios")
def list_scenarios():
    """
    返回支持的业务场景列表，供客户端渲染下拉选项。

    返回:
        [{"id": "...", "label": "..."}, ...]
    """
    return [
        {"id": "market_research", "label": "Market Research Report"},
        {"id": "social_media", "label": "Social Media Content"},
    ]


@app.get("/health")
def health():
    """
    健康检查端点，供负载均衡或容器编排探活。

    返回:
        {"status": "ok"}
    """
    return {"status": "ok"}
