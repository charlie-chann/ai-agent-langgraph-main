# 架构流程图 PNG

本目录包含 `architecture.md` 中全部 **23 张**流程图的 PNG 导出（含 `00` 总览与 `01`–`22`）。

> 代码目录：`app/knowledge`（知识基建）+ `app/tools`（Agent @tool）+ `app/api` / `services` / `agent` / `gateway` / `infrastructure` / `core`。

| 文件 | 说明 |
|------|------|
| `00_project_end_to_end.png` | 全项目端到端总览 |
| `01_layers_overview.png` | 六层架构总览 |
| `02_streamlit_ui.png` | Streamlit UI 全栈路径（经网关） |
| `03_eval_harness.png` | Eval Harness |
| `04_http_gateway.png` | HTTP 网关 |
| `05_jwt_rbac.png` | JWT + RBAC |
| `06_cache_rate_limit.png` | 缓存与限流 |
| `07_ask_sync.png` | ask() 同步 |
| `08_ask_stream.png` | ask_stream() |
| `09_hitl_resume.png` | HITL 恢复 |
| `10_startup.png` | 启动预热 |
| `11_langgraph_main.png` | LangGraph 主图 |
| `12_rag_state_flow.png` | RAGState 流转 |
| `13_checkpointer_hitl.png` | Checkpointer |
| `14_retrieval.png` | 检索 |
| `15_ingest.png` | 入库 |
| `16_conflict.png` | 冲突检测 |
| `17_knowledge_graph.png` | 知识图谱 |
| `18_provider_circuit_breaker.png` | Provider 熔断 |
| `19_timeouts.png` | 超时 |
| `20_compression.png` | 上下文压缩 |
| `21_docker_topology.png` | Docker |
| `22_conversations.png` | 会话存储 conversation_id + Postgres |

## 重新生成

```bash
# 1. 编辑 docs/diagrams/source/*.mmd 或 architecture.md 内折叠的 Mermaid 源码
# 2. 从 architecture.md 提取并渲染（需 Node.js + npx，或可用 Kroki 网络）
python scripts/render_diagrams.py

# 3. 刷新 architecture.md 中的图片引用（若脚本需要）
python scripts/update_architecture_images.py
```

图源文件位于 `source/` 子目录（`.mmd` 格式）。
