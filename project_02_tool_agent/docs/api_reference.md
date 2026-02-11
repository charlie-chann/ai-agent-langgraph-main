# API Reference — project_02_tool_agent

Base URL: `http://localhost:8002`

---

## POST `/chat`
Non-streaming agent run.

**Request**
```json
{ "message": "What time is it in Tokyo?", "chat_history": [] }
```

**Response**
```json
{
  "answer": "It is currently 2026-03-18 21:00:00 JST in Tokyo.",
  "steps": [
    {"tool": "get_datetime", "input": "Asia/Tokyo", "output": "2026-03-18 21:00:00 JST"}
  ],
  "latency_ms": 2100,
  "tool_calls": 1
}
```

---

## POST `/chat/stream`
SSE streaming. Returns `text/event-stream`.

**Events**
```
data: {"type": "token", "content": "It "}
data: {"type": "tool_start", "tool": "get_datetime", "input": "Asia/Tokyo"}
data: {"type": "tool_end", "output": "2026-03-18 21:00:00 JST"}
data: {"type": "final", "answer": "...", "steps": [...], "latency_ms": 2100}
data: [DONE]
```

---

## GET `/tools`
List all registered tools.

**Response**
```json
[
  {"name": "web_search", "description": "Search the web..."},
  {"name": "calculator", "description": "Evaluate a math..."},
  ...
]
```

---

## GET `/health`
```json
{ "status": "ok" }
```
