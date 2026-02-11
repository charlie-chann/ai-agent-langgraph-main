"""
api.py — 企业机器人 FastAPI HTTP 服务

【职责】
暴露 REST/SSE 接口：非流式聊天、流式聊天、历史查询/清除、
用户权限查询及健康检查，供前端或其他微服务集成。

【设计原因】
与 Streamlit UI 解耦，便于企业内网以 API 方式嵌入门户或移动端；
流式端点采用 SSE 协议，满足打字机效果演示需求。
"""
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
    """聊天请求体：用户消息与可选用户名（默认演示账号 emp_charlie）。"""

    message: str
    username: str = "emp_charlie"


class ClearRequest(BaseModel):
    """清除历史请求体：指定要清空会话的用户名。"""

    username: str


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    非流式聊天接口：同步返回完整 Agent 响应及元数据。

    RBAC 在 agent.chat 内部按 username 自动生效。
    """
    result = chat(req.username, req.message)
    return result


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    SSE 流式聊天接口：将最终答案按词拆分逐 token 推送（演示用途）。

    注意：底层仍调用完整 chat()，非真正的 LLM token 级流式。
    """
    def _gen():
        """SSE 事件生成器：先逐词推送 answer，再推送 done 元数据。"""
        result = chat(req.username, req.message)
        # 按空格分词模拟 token 流，便于前端展示打字效果
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
    """
    查询指定用户当前内存中的历史消息条数（不返回全文，仅统计）。

    Args:
        username: 路径参数，用户账号
    """
    history = get_history(username)
    return {"username": username, "messages": len(history)}


@app.post("/history/clear")
async def clear_chat_history(req: ClearRequest):
    """
    清除指定用户的 Agent 侧对话记忆。

    Args:
        req: 含 username 的请求体
    """
    clear_history(req.username)
    return {"cleared": True, "username": req.username}


@app.get("/user/{username}/permissions")
async def user_permissions(username: str):
    """
    返回用户的 RBAC 角色及允许调用的工具名称列表。

    供集成方在调用 /chat 前做权限预检或 UI 展示。
    """
    return {
        "username": username,
        "role": get_user_role(username),
        "allowed_tools": get_allowed_tools(username),
    }


@app.get("/health")
def health():
    """存活探针：负载均衡/K8s 健康检查用。"""
    return {"status": "ok"}
