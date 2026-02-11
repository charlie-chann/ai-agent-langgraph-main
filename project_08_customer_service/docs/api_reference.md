# docs/api_reference.md — 客服 Agent API 文档

Base URL: `http://localhost:8008`

## 接口列表

### `POST /chat/stream`
SSE 流式对话接口

**请求体：**
```json
{ "message": "我的订单ORD2024001到哪了？", "user_id": "u001", "model": null }
```
**响应：** `text/event-stream`
```
data: {"text": "[情感分析] 负面评分: 0.00 | 需升级: false\n"}
data: {"text": "[工具 1: query_order_status] {\"found\": true, \"status\": \"已签收\" ...}"}
data: {"text": "您好！您的订单 ORD2024001 已于 "}
data: {"text": "7天前成功签收。 "}
data: [DONE]
```

---

### `POST /chat`
同步对话接口

**响应：**
```json
{
  "output": "您好！根据查询，您的订单...",
  "user_id": "u001",
  "sentiment": {"score": 0.0, "needs_escalation": false},
  "steps": [{"tool": "classify_intent", "output": "..."}]
}
```

---

### `POST /kb/search`
知识库搜索

**请求：** `{ "query": "退款流程" }`

**响应：**
```json
{
  "found": true,
  "results": [
    { "id": "faq_004", "category": "退换货", "question": "如何申请退款？", "answer": "..." }
  ]
}
```

---

### `POST /order/status`
查询订单

**请求：** `{ "order_id": "ORD2024001" }`

---

### `POST /ticket/create`
创建工单

**请求：**
```json
{
  "user_id": "u001",
  "title": "APP无法登录",
  "description": "点击登录后没有反应",
  "intent": "technical_support"
}
```

---

### `POST /sentiment`
情感分析

**请求：** `{ "query": "你们是骗子！" }`

**响应：**
```json
{ "sentiment": "negative", "score": 0.9, "needs_escalation": true }
```

---

### `GET /health`
```json
{ "status": "ok", "service": "customer_service_agent", "port": 8008 }
```
