# docs/architecture.md — 客服 Agent 架构设计

## 系统架构图

```
用户/API
    │
    ▼
┌──────────────────────────────────────────┐
│            Streamlit UI（4模式）          │
│  智能客服 | 订单查询 | 工单管理 | 知识库  │
└─────────────────┬────────────────────────┘
                  │
         ┌────────▼────────┐
         │   ReAct Agent   │ ← qwen3.5:latest
         │  (LangChain)    │
         └────────┬────────┘
                  │ 工具调用派发
    ┌─────────────┼──────────────────┬──────────────┐
    ▼             ▼                  ▼              ▼
sentiment    kb_tool           ticket_tool    order_tool
_tool       (BM25搜索)         (工单CRUD)    (订单查询)
    │              │                 │              │
关键词评分   FAQ JSON文件       内存存储       模拟订单DB
自动升级判断  12篇中文FAQ      P1-P4优先级   物流轨迹数据
```

## Agent 对话流程

```
用户发送消息
      │
      ▼
预检：analyse_sentiment（情感分析）
      │
      │──→ score ≥ 0.7? 标记需要升级
      │
      ▼
classify_intent（意图分类）
      │
┌─────┴─────────────────────────────────┐
│ 意图路由                                │
├── query_faq → search_kb               │
├── order_status → query_order_status   │
├── complaint/refund → create_ticket    │
├── technical_support → search_kb       │
│                      + create_ticket  │
└── account_issue → search_kb           │
      │
      ▼
生成最终回复（中文，友好专业）
      │
      ▼
[if needs_escalation] → escalate_ticket
      │
      ▼
更新会话记忆
```

## 工具集（11个工具）

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `analyse_sentiment` | 负面情感评分（0-1） | 规则词典 |
| `classify_intent` | 意图分类（7类） | 规则词典 |
| `search_kb` | FAQ全文搜索 | knowledge_base/faq.json |
| `list_kb_categories` | 知识库分类列表 | knowledge_base/faq.json |
| `create_ticket` | 创建工单（含SLA） | 内存存储 |
| `get_ticket` | 查询工单详情 | 内存存储 |
| `list_user_tickets` | 查询用户工单列表 | 内存存储 |
| `update_ticket_status` | 更新工单状态 | 内存存储 |
| `escalate_ticket` | 升级至人工客服 | 内存存储 |
| `query_order_status` | 查询订单+物流 | 模拟数据库 |
| `list_user_orders` | 查询用户订单列表 | 模拟数据库 |

## 会话记忆设计

```python
# 用户级别记忆字典
_SESSION_MEMORY: dict[str, list[dict]] = {
    "u001": [
        {"role": "user", "content": "密码忘了"},
        {"role": "assistant", "content": "您可以通过以下步骤..."},
        ...
    ]
}
# 最多保留最近20条消息（10轮对话）
```

## 升级规则

| 触发条件 | 动作 |
|---------|------|
| 情感负面分 ≥ 0.7 | 标记 needs_escalation=True，UI显示红色警告 |
| 工单 intent=complaint 且 priority=P1 | 自动调用 escalate_ticket |
| 用户使用威胁性词汇（骗子/起诉/律师等） | 评分立即 ≥ 0.85 |
