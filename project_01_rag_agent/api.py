# api.py — FastAPI with SSE streaming endpoint
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
    message: str
    chat_history: List[dict] = []


class IngestResponse(BaseModel):
    chunks: int
    files: List[str]


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE streaming chat endpoint."""
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
    """Non-streaming chat endpoint."""
    result = ask(req.message, req.chat_history)
    return result


@app.post("/ingest", response_model=IngestResponse)
async def ingest(files: List[UploadFile] = File(...)):
    """Upload and ingest documents into the vector store."""
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
    return {"status": "ok"}
