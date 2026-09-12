# project_00_rag_agent — Production RAG

Enterprise-grade RAG with LangGraph, JWT/RBAC, Redis cache, Knowledge Graph, HITL, and full Docker stack.

## Features

| Layer | Capabilities |
|-------|-------------|
| **Provider** | Switchable `ollama` / `openai` |
| **Retrieval** | Hybrid + ACL + Rerank + BM25 persistence |
| **KG** | Rule + LLM NER extraction (`hybrid` mode) |
| **HITL** | `interrupt_before` + Postgres/Memory checkpointer |
| **Auth** | JWT + RBAC |
| **Cache** | Redis + in-memory fallback |
| **UI** | Streamlit（HTTP 客户端，经 FastAPI） |
| **Eval** | Integrated with `eval/harness` (`--project 00`) |

## Quick Start

```bash
cd project_00_rag_agent

# 1. 安装依赖（必须，含 chromadb / rank-bm25）
pip install -r requirements.txt

# 2. 配置本地环境（推荐）
cp .env.local.example .env.local
# 或兼容旧方式：cp .env.example .env

# 3. 确保 Ollama 在跑并已拉模型
ollama pull qwen2.5:1.5b
ollama pull nomic-embed-text

# 4. 一键启动（入库样例 + API）
bash scripts/start_local.sh

# 5. 另开终端启动 UI（需先登录，默认 admin/admin123）
streamlit run app_ui.py --server.port 8501
```

**访问：**
- API 文档：http://localhost:8000/docs
- Streamlit UI：http://localhost:8501
- 默认账号：`admin` / `admin123`
- 确认环境：`curl http://localhost:8000/health` → 应看到 `"app_env":"local"`

## Environments (local / test / prod)

用 `APP_ENV` 区分环境，**不要**在业务代码里根据 URL 写 if。

| 环境 | 配置文件 | 启动方式 |
|------|----------|----------|
| 本地 `local` | `.env.local`（从 `.env.local.example` 复制） | `export APP_ENV=local`（默认） |
| 测试 `test` | `.env.test`（从 `.env.test.example` 复制） | `export APP_ENV=test` |
| 生产 `prod` | `.env.prod`（从 `.env.prod.example` 复制，**勿提交 Git**） | `export APP_ENV=prod` |

加载优先级：进程环境变量 > `.env.{APP_ENV}` > `.env`  
生产护栏：`APP_ENV=prod` 时弱 `JWT_SECRET`（默认值或长度 &lt; 32）会导致**启动失败**。

Java 侧应对齐各环境的 `API_BASE_URL`（测试打测试域名，生产打生产域名）。

**常见问题：**
- `Could not import chromadb` → `pip install -r requirements.txt`
- Ingest 很慢 → `.env.local` 里设 `KG_EXTRACTION_MODE=rule`（默认已是 rule）
- Redis 连接失败 → 可忽略，自动降级内存缓存/限流

## Docker (Full Stack)

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull nomic-embed-text

# API:  http://localhost:8000/docs
# UI:   http://localhost:8501  (login admin/admin123)
```

## Auth

| User | Password | Role |
|------|----------|------|
| admin | admin123 | admin |
| editor | editor123 | editor |
| viewer | viewer123 | viewer |

## Eval Harness

```bash
# From repo root
python eval/harness/run_eval.py --project 00 --prompt v1
python eval/harness/run_eval.py --project 00 --prompt v1 --update-baseline
python eval/harness/run_eval.py --project 00 --prompt v2 --regression
```

## Project Structure

```
project_00_rag_agent/
│
├── main.py
├── app_ui.py
├── config.py                        # 兼容 shim → app.core.config
│
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   ├── errors.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── chat.py
│   │       ├── ingest.py
│   │       ├── hitl.py
│   │       └── health.py
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── ingest.py
│   │   ├── hitl.py
│   │   └── common.py
│   ├── services/
│   │   ├── agent_service.py
│   │   ├── chat_service.py
│   │   ├── stream_service.py
│   │   ├── ingest_service.py
│   │   ├── health_service.py
│   │   ├── hitl_service.py
│   │   └── warmup_service.py
│   ├── agent/
│   │   ├── factory.py
│   │   ├── checkpointer.py
│   │   ├── graphs/
│   │   │   ├── rag/
│   │   │   └── react/
│   │   └── prompts/
│   │       ├── rag.py
│   │       └── react.py
│   ├── knowledge/                   # 知识库基建：入库、检索、KG、冲突
│   │   ├── retriever.py
│   │   ├── ingest.py
│   │   ├── conflict.py
│   │   ├── knowledge_graph.py
│   │   └── kg_extractor.py
│   ├── tools/                       # Agent 可调用 @tool（ReAct / bind_tools）
│   │   ├── registry.py
│   │   └── knowledge.py
│   ├── gateway/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   └── request_context.py
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── conversations.py
│   │   │   └── stream_wal.py
│   │   ├── providers/
│   │   │   └── factory.py
│   │   ├── cache/
│   │   │   └── redis_cache.py
│   │   └── observability/
│   │       └── metrics.py
│   └── core/
│       ├── config.py                # 全局配置（权威位置）
│       ├── exceptions.py
│       ├── timeouts.py
│       ├── circuit_breaker.py
│       ├── compression.py
│       ├── streaming.py
│       └── stream_sse.py
│
├── tests/
│   ├── api/
│   ├── services/
│   ├── agent/
│   ├── knowledge/
│   └── tools/
│
├── docs/
│   └── diagrams/
│
├── scripts/
└── sample_docs/
```

See [docs/architecture.md](docs/architecture.md) for HITL, KG, and Docker details.
