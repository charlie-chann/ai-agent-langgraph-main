# docs/api_reference.md — Code Agent API

Base URL: `http://localhost:8006`

## Endpoints

### `POST /agent/stream`
Stream agent response as SSE.

**Request body:**
```json
{ "task": "Write a binary search function in Python", "model": null }
```
**Response:** `text/event-stream`
```
data: {"text": "[Tool 1: execute_python] Output: ..."}
data: {"text": "Here is the binary search implementation..."}
data: [DONE]
```

---

### `POST /agent/invoke`
Run agent and return full result JSON.

**Response:**
```json
{
  "output": "Here is the binary search...",
  "steps": [["execute_python", "def binary_search..."], "4"]
}
```

---

### `POST /execute`
Execute Python code directly (no agent loop).

**Request:**
```json
{ "code": "print(sum(range(10)))" }
```
**Response:**
```json
{ "output": "45" }
```

---

### `POST /review`
AI code review.

**Request:**
```json
{ "code": "def div(a,b): return a/b", "language": "python" }
```
**Response:**
```json
{ "review": "## Summary\n❌ Missing division-by-zero check..." }
```

---

### `GET /health`
```json
{ "status": "ok", "service": "code_agent", "port": 8006 }
```
