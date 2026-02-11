# API Reference — project_01_rag_agent

Base URL: `http://localhost:8001`

---

## POST `/chat`
Non-streaming chat.

**Request**
```json
{ "message": "What is RAG?", "chat_history": [] }
```

**Response**
```json
{
  "answer": "RAG (Retrieval-Augmented Generation) is...",
  "sources": ["doc1.pdf"],
  "latency_ms": 3200,
  "iterations": 1
}
```

---

## POST `/chat/stream`
SSE streaming chat. Returns `text/event-stream`.

**Events**
```
data: {"token": "RAG"}
data: {"token": " stands"}
...
data: {"sources": ["doc1.pdf"], "latency_ms": 3200, "__meta__": true}
data: [DONE]
```

---

## POST `/ingest`
Upload documents (multipart/form-data).

**Form field**: `files` (multiple)  
**Accepted types**: `.pdf`, `.txt`, `.md`, `.docx`

**Response**
```json
{ "chunks": 128, "files": ["report.pdf", "notes.md"] }
```

---

## GET `/health`
```json
{ "status": "ok" }
```
