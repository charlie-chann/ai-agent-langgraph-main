"""
api.py — FastAPI HTTP 接口层

【职责】
把 RAG 能力暴露为 REST API，供前端、移动端、其他微服务调用。

【与 app.py 的关系】
- app.py：Streamlit 人机界面，面向演示和内部试用
- api.py：无 UI 的纯接口，面向系统集成

【端点一览】
  GET  /health        — 健康检查（负载均衡/K8s 探针）
  POST /chat          — 同步问答
  POST /chat/stream   — SSE 流式问答
  POST /ingest        — 上传文件并建立索引

【SSE 说明】
/chat/stream 使用 Server-Sent Events，客户端可逐 token 渲染，类似 ChatGPT 打字效果。
"""
import json
from pathlib import Path
from typing import List

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger

from agent import ask_stream, ask
from tools.ingest import load_documents, split_documents
from tools.retriever import build_vectorstore

app = FastAPI(title="RAG Agent API", version="1.0")


class ChatRequest(BaseModel):
    """聊天请求体：用户消息 + 可选的多轮历史（dict 格式，LangChain 可转换）。"""
    message: str
    chat_history: List[dict] = []


class IngestResponse(BaseModel):
    """文档摄入结果：切分了多少 chunk、处理了哪些文件名。"""
    chunks: int
    files: List[str]


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    SSE 流式聊天。

    每个 event 格式：
      data: {"token": "..."}   — 正文 token
      data: {...metadata...}   — 来源与耗时（agent 的 __META__）
      data: [DONE]             — 结束标记
    """
    def _gen():
        for token in ask_stream(req.message, req.chat_history):
            if token.startswith("\n\n__META__"):
                meta = token.replace("\n\n__META__", "")
                yield f"data: {meta}\n\n"
            else:
                payload = json.dumps({"token": token})
                yield f"data: {payload}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    非流式聊天：等待完整 LangGraph 执行完毕（含自校正重试），一次返回 JSON。

    返回字段：answer, sources, latency_ms, iterations, grade, error
    """
    result = ask(req.message, req.chat_history)
    return result


@app.post("/ingest", response_model=IngestResponse)
async def ingest(files: List[UploadFile] = File(...)):
    """
    上传一个或多个文件，执行 load → split → build_vectorstore。

    文件先存 /tmp/rag_uploads/，再交给 ingest 流水线。
    与 Streamlit 侧边栏上传逻辑等价，只是通过 HTTP multipart 传入。
    """
    tmp_dir = Path("/tmp/rag_uploads")
    tmp_dir.mkdir(exist_ok=True)
    saved_paths = []
    for f in files:
        dest = tmp_dir / f.filename
        content = await f.read()
        dest.write_bytes(content)
        saved_paths.append(dest)
        logger.info(f"Saved upload: {f.filename}")

    docs = load_documents(saved_paths)
    if not docs:
        raise HTTPException(status_code=400, detail="No supported documents found")
    chunks = split_documents(docs)
    build_vectorstore(chunks)

    return IngestResponse(chunks=len(chunks), files=[f.filename for f in files])


@app.get("/health")
def health():
    """存活探针：返回 {"status": "ok"} 表示服务进程正常。"""
    return {"status": "ok"}
