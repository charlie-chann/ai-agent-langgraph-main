# 🛠️ Project 02 — Multi-Tool ReAct Agent (v2.0)

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
企业日常工作需要同时查询多个数据源、做计算、读写文件——现有 ChatBot 无法跨工具协作。
ReAct Agent 实现"思考-行动-观察"循环，自主决定调用哪个工具、用几次，完成复杂多步任务。

- **效率提升**：一句话触发多个工具链，替代人工多窗口切换
- **可溯源**：每步工具调用有完整日志，满足企业审计需求
- **可扩展**：新增工具只需添加 `@tool` 装饰器，无需改主流程
- **本地安全**：LLM 本地运行，工具调用结果不离开企业网络

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| LangChain Hub Agents | 完善生态 | 需要外部 API keys |
| AutoGPT | 知名度高 | 不稳定，成本高 |
| OpenAI Assistants API | 官方支持 | 数据上云，贵 |
| **本项目** | 本地运行，零 API 费用，完全可控 | 需要自建工具 |

---

## 项目简介

基于 LangGraph 的**多工具 ReAct Agent**，内置工具：

- ✅ 网络搜索 (DuckDuckGo)
- ✅ 数学计算 (安全 AST)
- ✅ 文件读写 (沙箱)
- ✅ 时区时间查询

使用 `langgraph.prebuilt.create_react_agent` 架构，简洁高效。

---

## 技术架构

```
用户问题
    │
    ▼
┌─────────────────────────────────────────┐
│     LangGraph ReAct Agent (LangGraph)   │
│                                         │
│  messages: [HumanMessage, ...]          │
│       │                                 │
│       ▼                                 │
│  ┌──────────────────────────────────┐   │
│  │     Tool Router (自动选择)        │   │
│  │  web_search │ calculator │ file_  │   │
│  │  read/write │ datetime             │   │
│  └──────────────────────────────────┘   │
│       │                                 │
│  Observation: 结果反馈                   │
│       │                                 │
│  Final Answer (AI Message)              │
└─────────────────────────────────────────┘
```

---

## 快速开始

```bash
cd project_02_tool_agent
uv pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3.5:latest

# UI
uv run streamlit run app.py

# API
uv run uvicorn api:app --reload --port 8002
```

---

## 内置工具

| 工具 | 功能 | 示例 |
|------|------|------|
| `web_search` | DuckDuckGo 搜索 | "今天北京天气" |
| `calculator` | 安全数学计算 | "2**10 + 5*3" |
| `file_read` | 读取沙箱文件 | "notes.txt" |
| `file_write` | 写入沙箱文件 | "summary.txt" |
| `file_list` | 列出沙箱文件 | "" |
| `get_datetime` | 时区时间查询 | "Asia/Shanghai" |

---

## Python API

```python
from agent import run, run_stream

# 同步调用
result = run("What's 15 + 27?")
print(result["answer"])
print(f"Tool calls: {result['tool_calls']}")

# 流式调用
for event in run_stream("Search for AI news"):
    if event["type"] == "token":
        print(event["content"], end="")
    elif event["type"] == "tool_end":
        print(f"\n[Tool: {event['tool']}] {event['output'][:100]}")
```

---

## 后续改进方向

- [ ] 接入 Slack/Email 工具（企业通讯集成）
- [ ] 接入 SQL 查询工具（数据库能力）
- [ ] 接入 Python REPL（数据分析）
- [ ] Plan-and-Execute 模式（先规划再执行）
- [ ] 工具结果缓存（减少重复搜索）
