# Architecture — Enterprise RAG + Agentic RAG

## 系统组件

```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit UI (app.py)                  │
│  ┌──────────────┐   ┌─────────────────────────────────────┐ │
│  │   Sidebar    │   │         Chat Area (streaming)        │ │
│  │ - Upload docs│   │  user msg → spinner → tokens → done  │ │
│  │ - Model sel. │   │  [Sources expander]                  │ │
│  │ - Metrics    │   └─────────────────────────────────────┘ │
│  └──────────────┘                                           │
└────────────────────────────┬────────────────────────────────┘
                             │ ask_stream()
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   LangGraph Agent (agent.py)                │
│                                                             │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│   │ Rewrite  │───▶│ Retrieve │───▶│ Generate │             │
│   │ (LLM)   │    │ (Hybrid) │    │ (Stream) │             │
│   └──────────┘    └──────────┘    └────┬─────┘             │
│        ▲                               │                   │
│        │         ┌──────────┐          │                   │
│        └─────────│  Grade   │◀─────────┘                   │
│       (retry)    │ (LLM)   │  score=no                     │
│                  └──────────┘                               │
└─────────────────────────────────────────────────────────────┘
                             │
           ┌─────────────────┴──────────────────┐
           ▼                                    ▼
┌──────────────────┐                 ┌──────────────────────┐
│   BM25 Retriever │                 │  ChromaDB + Ollama   │
│   (sparse, fast) │                 │  nomic-embed-text    │
│   rank-bm25      │                 │  (dense semantic)    │
└──────────────────┘                 └──────────────────────┘
           │                                    │
           └─────────────┬──────────────────────┘
                         ▼
               ┌──────────────────┐
               │  Reranker        │
               │  (keyword score) │
               └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │  Top-K Chunks    │
               │  + Source meta   │
               └──────────────────┘
```

## 数据流向

1. **Ingest**: 用户上传文件 → Loader → Chunker → Embedder (Ollama) → ChromaDB 持久化
2. **Ask**: 问题 → (可选 Rewrite) → Hybrid Retrieve → Rerank → LLM Generate (stream) → Grade
3. **Retry**: Grade=no → Rewrite 增强 → 重新检索 → 重新生成（最多 2 次）

## 安全边界
- 所有 LLM 调用 → localhost:11434（不出网络）
- 文档上传临时存储 → `/tmp/rag_uploads`（可配置为内存或 S3）
- 无用户 PII 传出
