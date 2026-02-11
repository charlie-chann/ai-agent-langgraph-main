# docs/api_reference.md — Finance Agent API

Base URL: `http://localhost:8007`

## Endpoints

### `POST /agent/stream`
Stream agent response as SSE.

**Request:**
```json
{ "task": "Analyse Apple (AAPL) fundamentals", "model": null }
```
**Response:** `text/event-stream`
```
data: {"text": "[Tool 1/4: get_stock_quote] {\"price\": 182.50 ...}"}
data: {"text": "Apple (AAPL) currently trades at $182.50..."}
data: [DONE]
```

---

### `POST /agent/invoke`
Full agent run, returns JSON.

**Response:**
```json
{
  "output": "## AAPL Analysis\n...",
  "steps": [{"tool": "get_stock_quote", "input": "AAPL", "output": "..."}]
}
```

---

### `POST /quote`
Direct stock quote (no agent loop).

**Request:**
```json
{ "ticker": "AAPL" }
```
**Response:**
```json
{ "ticker": "AAPL", "price": 182.50, "pe_ratio": 28.4, "beta": 1.2 ... }
```

---

### `POST /compliance/screen`
Portfolio compliance screening.

**Request:**
```json
{
  "portfolio": [
    {"ticker": "AAPL", "weight": 0.25, "sector": "Technology", "volatility": 0.28}
  ]
}
```
**Response:**
```json
{
  "overall_status": "⚠️ NEEDS REVIEW",
  "violations": [],
  "warnings": ["⚠️ Technology sector overweight (75.0%)"],
  "passed_checks": ["✅ AAPL: 25.0%"]
}
```

---

### `POST /analysis/fundamentals`
Score a set of financial metrics.

**Request:**
```json
{
  "metrics": {
    "pe": 25, "pb": 3.2, "roe": 0.18, "net_margin": 0.22,
    "debt_to_equity": 80, "current_ratio": 1.5,
    "revenue_growth": 0.08, "earnings_growth": 0.12, "beta": 1.1
  }
}
```

---

### `GET /health`
```json
{ "status": "ok", "service": "finance_agent", "port": 8007 }
```
