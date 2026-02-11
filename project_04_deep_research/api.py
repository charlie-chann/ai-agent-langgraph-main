"""
api.py — Deep Research Agent FastAPI 服务

【职责】
暴露 REST 端点：同步研究、SSE 流式研究与健康检查，供前端或外部系统调用 Agent。

【设计原因】
HTTP 层与 agent 业务解耦，便于独立部署 API 服务；
StreamingResponse 实现 Server-Sent Events，与 Streamlit 共用同一 research_stream 逻辑。
"""
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import research, research_stream

app = FastAPI(title="Deep Research Agent API", version="1.0")


class ResearchRequest(BaseModel):
    """POST /research 与 /research/stream 的请求体。"""
    topic: str


@app.post("/research")
async def run_research(req: ResearchRequest):
    """
    同步执行完整研究流水线，返回报告与元数据 JSON。

    Args:
        req: 含 topic 字段的请求体

    Returns:
        final_report、research_notes、coverage 等关键字段
    """
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
    """
    SSE 流式研究：每完成一个图节点推送一条 data 事件，结束时发送 [DONE]。

    Args:
        req: 含 topic 字段的请求体

    Returns:
        text/event-stream 格式的 StreamingResponse
    """
    def _gen():
        for event in research_stream(req.topic):
            # ensure_ascii=False 保证中文 preview 正常编码
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/health")
def health():
    """
    健康检查端点，供负载均衡或容器编排探活。

    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}
