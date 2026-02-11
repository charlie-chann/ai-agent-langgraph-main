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

# 2. 配置环境
cp .env.example .env

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

**常见问题：**
- `Could not import chromadb` → `pip install -r requirements.txt`
- Ingest 很慢 → `.env` 里设 `KG_EXTRACTION_MODE=rule`（默认已是 rule）
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
├── config.py
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── README.md
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
│   │   ├── rag_service.py
│   │   └── warmup_service.py
│   ├── agent/
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── nodes.py
│   │   │   ├── edges.py
│   │   │   ├── builder.py
│   │   │   └── checkpointer.py
│   │   └── prompts/
│   │       └── rag_prompts.py
│   ├── retrieval/
│   │   ├── retriever.py
│   │   ├── ingest.py
│   │   ├── conflict.py
│   │   ├── knowledge_graph.py
│   │   └── kg_extractor.py
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
│   └── retrieval/
│
├── docs/
│   └── diagrams/
│
├── scripts/
└── sample_docs/
```

See [docs/architecture.md](docs/architecture.md) for HITL, KG, and Docker details.
