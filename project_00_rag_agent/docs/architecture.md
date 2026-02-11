# project_00_rag_agent — 分层架构与核心流程

> **流程图已导出为 PNG**：见 [`docs/diagrams/`](./diagrams/)。修改图源文件 `docs/diagrams/source/*.mmd` 后执行 `python scripts/render_diagrams.py` 重新生成。

> 生产级 RAG Agent：LangGraph + JWT/RBAC + Hybrid 检索 + 知识图谱 + HITL + Redis 缓存

---

## 一、目录结构总览

```
project_00_rag_agent/
├── agent.py                 # 对外入口：ask / ask_stream / resume_hitl / startup
├── api.py                   # FastAPI HTTP 层
├── app.py                   # Streamlit UI（Local / API 双模式）
├── config.py                # pydantic-settings 全量配置
│
├── core/                    # 横切能力
│   ├── compression.py       # 对话压缩 + RAG context 预算
│   ├── timeouts.py          # LLM 调用超时
│   ├── circuit_breaker.py   # LLM/Embed 熔断
│   └── exceptions.py        # 结构化错误码
│
├── middleware/              # 网关中间件
│   ├── auth.py              # JWT + RBAC
│   ├── cache.py             # Redis 答案缓存
│   ├── rate_limit.py        # 限流
│   └── request_context.py   # request_id
│
├── providers/               # 模型 Provider 抽象
│   └── factory.py           # Ollama / OpenAI 切换
│
├── graph/                   # LangGraph 核心
│   ├── state.py             # RAGState
│   ├── nodes.py             # guard/rewrite/retrieve/generate/grade/hitl
│   ├── edges.py             # 条件路由
│   ├── builder.py           # 编译图 + interrupt_before
│   └── checkpointer.py      # Memory / Postgres 持久化
│
├── tools/                   # 业务工具
│   ├── retriever.py         # Hybrid + ACL + Rerank + KG
│   ├── ingest.py            # 安全入库
│   ├── knowledge_graph.py   # 三元组存储/查询
│   ├── kg_extractor.py      # 规则 + LLM NER 抽取
│   └── conflict.py          # 文档冲突检测
│
├── prompts/rag_prompts.py   # guard / rewrite / rag / grade
├── observability/metrics.py # 指标计数
├── tests/                   # 单元 + API + 集成测试
├── sample_docs/             # 样例知识库
├── Dockerfile + docker-compose.yml
└── docs/architecture.md     # 本文档
```

---

## 二、六层架构（自上而下）

**阅读顺序**：先看本图建立全栈心智模型 → 再按层阅读第三节～第八节（每层有职责说明 + 专属流程图）。

![六层架构总览](./diagrams/01_layers_overview.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TB
    subgraph L1["① 客户端层 Client"]
        ST[Streamlit app.py]
        CLI[curl / SDK / Eval Harness]
    end

    subgraph L2["② 网关层 Gateway"]
        API[api.py FastAPI]
        AUTH[JWT + RBAC]
        RL[Rate Limit]
        CACHE[Redis Cache]
        RID[request_id]
    end

    subgraph L3["③ 编排层 Orchestration"]
        AGENT[agent.py]
        COMP[compression 压缩]
    end

    subgraph L4["④ 图引擎层 LangGraph"]
        GRAPH[guard→hitl→rewrite→retrieve→generate→grade]
        CP[Checkpointer Postgres/Memory]
    end

    subgraph L5["⑤ 工具层 Tools"]
        RET[retriever 混合检索]
        ING[ingest 入库]
        KG[knowledge_graph]
        CONF[conflict 冲突]
    end

    subgraph L6["⑥ 基础设施层 Infrastructure"]
        PROV[Provider Ollama/OpenAI]
        CB[Circuit Breaker]
        CHROMA[(ChromaDB)]
        BM25[(BM25 pickle)]
        KGSTORE[(KG pkl/json)]
        REDIS[(Redis)]
        PG[(Postgres checkpoint)]
    end

  ST -->|API 模式 HTTP| API
  ST -.->|Local 模式 进程内直连| AGENT
  CLI --> API
  API --> AUTH --> RL --> CACHE --> RID
  RID --> AGENT --> COMP --> GRAPH
  GRAPH --> CP
  GRAPH --> RET
  GRAPH --> ING
  RET --> KG
  RET --> CONF
  RET --> PROV
  ING --> PROV
  RET --> CB
  ING --> CB
  RET --> CHROMA & BM25
  KG --> KGSTORE
  CACHE --> REDIS
  CP --> PG
```

</details>

### 2.1 分层阅读索引（全栈 → 每层做什么）

| 层 | 职责（一句话） | 主要代码 | 本文章节 | 核心流程图 |
|----|----------------|----------|----------|------------|
| **① 客户端** | 收集输入、展示结果；API 模式发 HTTP，Local 模式直连 agent | `app.py`, eval harness | **三** | `02` UI 全栈路径、`03` Eval |
| **② 网关** | 鉴权、限流、缓存、request_id；**仅 API 部署走此层** | `api.py`, `middleware/*` | **四** | `04` 网关入口、`05` JWT、`06` 缓存限流 |
| **③ 编排** | 压缩历史、查缓存、组装 state、调用 LangGraph | `agent.py` | **五** | `07` ask、`08` ask_stream、`09` HITL resume、`10` startup |
| **④ 图引擎** | guard/HITL/改写/检索/生成/评分的有状态工作流 | `graph/*` | **六** | `11` 主图、`12` State、`13` Checkpointer |
| **⑤ 工具** | 入库、混合检索、KG、冲突检测 | `tools/*` | **七** | `14` 检索、`15` ingest、`16` 冲突、`17` KG |
| **⑥ 基础设施** | 模型调用、熔断、超时、持久化存储 | `providers/`, `core/`, 磁盘/Redis/PG | **八** | `18` 熔断、`19` 超时、`20` 压缩、`21` Docker |

**两条部署路径（务必区分）：**

| 路径 | 客户端 → 后端 | 何时使用 |
|------|----------------|----------|
| **生产 / API 模式** | Streamlit → **② 网关** → ③ → ④ → ⑤ → ⑥ → JSON 回 UI → 展示 | `Use API backend` 开启 |
| **本地 / Local 模式** | Streamlit → **③ agent 直连**（跳过 ②）→ ④ → ⑤ → ⑥ → 流式/元数据回 UI | 默认本地开发 |

`02_streamlit_ui` 图同时画出上述两条路径；**不是** UI 自己生成答案，中间必经 ③～⑥（API 模式还多一层 ②）。

---

## 三、层 1：客户端层

**本层职责**：人机交互、会话状态（`messages` / `token` / `thread_id`）、把用户操作转为 HTTP 或进程内调用；**不负责**检索与生成。

### 3.1 Streamlit UI 全栈路径（`app.py`）

下图在 **① 客户端视角** 画出完整调用链：API 模式经 **② 网关** 再进入 **③～⑥**；Local 模式跳过网关直连 agent。终点 `SHOW` 是网关/agent 返回 JSON 或流式 token **之后** 的 UI 渲染。

![Streamlit UI 流程](./diagrams/02_streamlit_ui.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    START([用户打开 UI]) --> MODE{Use API backend?}

    MODE -->|否 Local| ROLE[侧边栏选角色 admin/editor/viewer]
    MODE -->|是 API| LOGIN[输入用户名密码]
    LOGIN --> TOKEN[POST /auth/token 经 ② 网关]
    TOKEN --> ROLE2[session 存 token + role]

    ROLE --> SETTINGS[Runtime Settings<br/>Local 模式生效]
    ROLE2 --> SETTINGS

    SETTINGS --> INGEST{上传文档?}
    INGEST -->|是 Local| ING_LOCAL[ingest_files 直连 ⑤ 工具层]
    INGEST -->|是 API| ING_API[POST /ingest]
    INGEST -->|否| CHAT

    ING_API --> GW_ING["② 网关<br/>限流→JWT→RBAC"]
    GW_ING --> ING_RUN[⑤ ingest_files]
    ING_LOCAL --> CHAT
    ING_RUN --> CHAT

    CHAT[用户输入问题] --> CHATMODE{API 模式?}

    CHATMODE -->|是| POST_CHAT[POST /chat]
    POST_CHAT --> GW_CHAT["② 网关<br/>限流→JWT→RBAC→缓存"]
    GW_CHAT --> AGENT["③ agent.ask"]
    AGENT --> STACK["④ LangGraph → ⑤ Tools → ⑥ LLM/存储"]
    STACK --> JSON[JSON 返回 ① UI]
    JSON --> HITL{hitl_pending?}

    CHATMODE -->|否| STREAM_LOCAL["③ ask_stream 直连<br/>跳过 ② 网关"]
    STREAM_LOCAL --> STACK_LOCAL["④～⑥ 同栈"]
    STACK_LOCAL --> SHOW

    HITL -->|是| WARN[UI 显示等待审批]
    HITL -->|否| SHOW[展示 answer + metadata]

    WARN --> ADMIN{admin Approve?}
    ADMIN -->|是| RESUME[POST /hitl/resume 经 ② 网关]
    RESUME --> SHOW
```

</details>

### 3.2 Eval Harness 流程（`eval/harness/run_eval.py`）

![Eval Harness 流程](./diagrams/03_eval_harness.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart LR
    E1[加载 rag_v1/v2 Prompt] --> E2[注入 project_00 rag_prompts]
    E2 --> E3[加载 rag_qa.jsonl]
    E3 --> E4[循环 ask return_state=True]
    E4 --> E5[规则分 + LLM Judge]
    E5 --> E6[trace 归因]
    E6 --> E7{--regression?}
    E7 -->|是| E8[对比 baseline.json]
    E7 -->|否| E9[写 results/]
```

</details>

---

## 四、层 2：网关层（`api.py` + `middleware/`）

### 4.1 请求总入口（所有 HTTP 请求）

![HTTP 网关入口](./diagrams/04_http_gateway.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    REQ([HTTP Request]) --> SKIP{/health /ready<br/>/auth/token?}
    SKIP -->|是| PASS[跳过限流]
    SKIP -->|否| RL[rate_limit_middleware<br/>Redis/内存计数]

    RL -->|超限| E429[429 Too Many Requests]
    RL -->|OK| ROUTE{路由分发}

    ROUTE --> AUTH_EP["/auth/token"]
    ROUTE --> CHAT_EP["/chat /chat/stream"]
    ROUTE --> INGEST_EP["/ingest"]
    ROUTE --> HITL_EP["/hitl/resume"]
    ROUTE --> OPS["/health /ready /stats /metrics"]

    CHAT_EP --> JWT{Bearer Token?}
    INGEST_EP --> JWT
    HITL_EP --> JWT
    OPS --> JWT2{需鉴权?}

    JWT -->|无效| E401[401]
    JWT -->|有效| RBAC{角色有 permission?}
    RBAC -->|否| E403[403]
    RBAC -->|是| HANDLER[业务 Handler]

    HANDLER --> RID[new_request_id]
    RID --> AGENT_CALL[调用 agent.py]
```

</details>

### 4.2 JWT 鉴权 + RBAC 流程（`middleware/auth.py`）

![JWT + RBAC](./diagrams/05_jwt_rbac.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    LOGIN([POST /auth/token]) --> CHECK[DEMO_USERS_JSON 校验]
    CHECK -->|失败| E401[401 Invalid credentials]
    CHECK -->|成功| JWT[create_access_token<br/>sub + role + exp]

    API([带 Token 的请求]) --> DECODE[decode_token HS256]
    DECODE -->|无效| E401b[401]
    DECODE --> PERM{require_permission}

    PERM -->|chat| R1[admin/editor/viewer ✓]
    PERM -->|ingest| R2[admin/editor ✓]
    PERM -->|hitl_approve| R3[admin only ✓]
    PERM -->|metrics| R4[admin only ✓]
    PERM -->|health/stats| R5[admin/editor/viewer ✓]
```

</details>

**角色权限表：**

| 角色 | chat | ingest | hitl_approve | metrics | health/stats |
|------|------|--------|--------------|---------|--------------|
| admin | ✓ | ✓ | ✓ | ✓ | ✓ |
| editor | ✓ | ✓ | ✗ | ✗ | ✓ |
| viewer | ✓ | ✗ | ✗ | ✗ | ✓ |

### 4.3 缓存 + 限流流程

![缓存与限流](./diagrams/06_cache_rate_limit.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    subgraph Cache["middleware/cache.py"]
        C1[ask 前 cache_key question+roles] --> C2{Redis 命中?}
        C2 -->|是| C3[直接返回答案 cached=true]
        C2 -->|否| C4[跑完整图]
        C4 --> C5{HITL/错误?}
        C5 -->|否| C6[cache_set TTL=3600s]
        C5 -->|是| C7[不写缓存]
    end

    subgraph RateLimit["middleware/rate_limit.py"]
        R1[每请求 incr key] --> R2{count > 60/min?}
        R2 -->|是| R3[429 + Retry-After]
        R2 -->|否| R4[放行]
    end

    INGEST_DONE[POST /ingest 成功] --> CLEAR[cache_delete_prefix rag:ask:]
```

</details>

---

## 五、层 3：编排层（`agent.py`）

### 5.1 `ask()` 同步问答主流程

![ask() 同步问答](./diagrams/07_ask_sync.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    START([ask question]) --> COMPRESS[compress_chat_history<br/>滑动窗口 + token 预算]

    COMPRESS --> CACHE{use_cache && Redis?}
    CACHE -->|命中| RET_CACHED[返回 cached 结果]
    CACHE -->|未命中| BUILD[_base_state<br/>question/roles/request_id/hitl]

    BUILD --> CONFIG[configurable thread_id]
    CONFIG --> INVOKE[get_graph.invoke]

    INVOKE --> PACK[打包 result<br/>answer/sources/grade/hitl_pending/...]
    PACK --> SAVE{可缓存?}
    SAVE -->|是| CACHE_SET[cache_set]
    SAVE -->|否| RETURN
    CACHE_SET --> RETURN([返回 dict])
    RET_CACHED --> RETURN
```

</details>

### 5.2 `ask_stream()` 流式问答流程

![ask_stream() 流式](./diagrams/08_ask_stream.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    START([ask_stream]) --> COMP[compress_chat_history]
    COMP --> G1[node_guard]
    G1 -->|blocked| OUT1[直接 yield 拒答]
    G1 -->|ok| R1[node_rewrite]
    R1 --> RET1[node_retrieve]
    RET1 --> TRIM[trim_context_chunks token 预算]
    TRIM --> STREAM["rag_prompt + LLM streaming<br/>逐 token yield"]
    STREAM --> G2[node_generate 补全 state]
    G2 --> GR[node_grade 质量评分]
    GR --> META[yield __META__ JSON<br/>sources/latency/grade]
```

</details>

### 5.3 `resume_hitl()` HITL 恢复流程

![HITL resume](./diagrams/09_hitl_resume.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    START([resume_hitl thread_id]) --> SNAP[graph.get_state]
    SNAP -->|无| ERR[No pending thread]
    SNAP -->|有| APPROVE{approved?}

    APPROVE -->|否| REJECT[update_state 拒答]
    REJECT --> END1([返回 rejected])

    APPROVE -->|是| UPDATE[update_state hitl_approved=true]
    UPDATE --> RESUME[graph.invoke None 从 interrupt 继续]
    RESUME --> FLOW[hitl_gate → rewrite → retrieve → generate → grade]
    FLOW --> END2([返回完整 answer])
```

</details>

### 5.4 启动预热（`startup()`）

![启动预热](./diagrams/10_startup.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart LR
    BOOT([api lifespan]) --> S1[startup rebuild_bm25_from_chroma]
    S1 --> S2[get_checkpointer setup Postgres]
    S2 --> READY[服务就绪]
```

</details>

---

## 六、层 4：图引擎层（LangGraph 核心）

### 6.1 完整 LangGraph 主图

![LangGraph 主图](./diagrams/11_langgraph_main.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    ENTRY([entry]) --> GUARD

    subgraph GUARD["node_guard 安全门控"]
        G1[检测 HITL 风险关键词] --> G2[LLM guard_prompt JSON]
        G2 -->|blocked| G3[error=blocked 直接拒答]
        G2 -->|pass| G4[继续]
    end

    GUARD --> ROUTE{route_after_guard}

    ROUTE -->|blocked| END1([END])
    ROUTE -->|hitl_required 且未批准| HITL

    subgraph HITL["node_hitl_gate ⏸ interrupt_before"]
        H1[设置 Awaiting approval]
    end

    HITL --> REWRITE
    ROUTE -->|正常| REWRITE

    subgraph REWRITE["node_rewrite 查询改写"]
        RW1{iterations==0?}
        RW1 -->|是| RW2[pass-through 原问题]
        RW1 -->|否| RW3[LLM rewrite_prompt 改写]
        RW3 -->|失败| RW2
    end

    REWRITE --> RETRIEVE

    subgraph RETRIEVE["node_retrieve 检索"]
        RT[retrieve_with_kg] --> CF[detect_conflicts]
        CF --> FMT[format_conflicts 写入 state]
    end

    RETRIEVE --> GENERATE

    subgraph GENERATE["node_generate 生成"]
        GN1[trim_context_chunks] --> GN2[rag_prompt + kg + conflicts]
        GN2 --> GN3[LLM 生成 answer]
        GN3 -->|失败| GN4[降级：检索摘要]
    end

    GENERATE --> GRADE

    subgraph GRADE["node_grade 质量评分"]
        GR1[grade_prompt JSON score] --> GR2{parse 失败?}
        GR2 -->|是| GR3[fail-open yes]
        GR2 -->|否| GR4[score yes/no]
        GR4 -->|no 且达上限| GR5[disclaimer 免责声明]
    end

    GRADE --> RETRY{should_retry}

    RETRY -->|grade=no 且 iter<max| REWRITE
    RETRY -->|否则| END2([END])
```

</details>

**图拓扑（ASCII 速览）：**

```
entry → guard ─┬─ blocked ──────────────────────────────→ END
               ├─ hitl_required ─→ hitl_gate ⏸ ─→ rewrite
               └─ 正常 ─────────────────────────────→ rewrite
rewrite → retrieve → generate → grade ─┬─ no 且 iter<max → rewrite
                                       └─ 否则 ───────────→ END
```

### 6.2 RAGState 字段流转

![RAGState 字段流转](./diagrams/12_rag_state_flow.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart LR
    subgraph Input
        Q[question]
        H[chat_history]
        R[user_roles]
    end

    subgraph AfterRetrieve
        D[context_docs]
        K[kg_context]
        S[sources]
        C[conflicts]
    end

    subgraph AfterGenerate
        A[answer]
        L[latency_ms]
    end

    subgraph AfterGrade
        G[grade]
        I[iterations++]
    end

    Q --> GUARD2[guard] --> RW[rewritten_question]
    RW --> D & K & S & C
    D & K & C --> A
    A --> G --> I
```

</details>

**RAGState 字段分组（`graph/state.py`）：**

| 分组 | 字段 | 说明 |
|------|------|------|
| 输入 | question, rewritten_question, chat_history | 用户问题与多轮历史 |
| 检索 | context_docs, kg_context, sources, conflicts | 文档 + KG 证据 + 冲突 |
| 生成 | answer, grade, grade_reason, iterations, latency_ms, disclaimer | 回答与自校正 |
| 安全 | error, hitl_required, hitl_approved | 拦截与人工审批 |
| 权限 | user_roles, request_id | ACL 与追踪 |

### 6.3 Checkpointer 与 HITL 中断

![Checkpointer + HITL](./diagrams/13_checkpointer_hitl.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    COMPILE[build_rag_graph] --> CP{CHECKPOINTER_BACKEND}
    CP -->|postgres| PG[PostgresSaver.setup]
    CP -->|memory/fallback| MEM[MemorySaver]

    PG & MEM --> INT[interrupt_before hitl_gate]

    INT --> RUN[graph.invoke thread_id]
    RUN -->|命中 HITL| PAUSE[图暂停 状态持久化到 PG]
    PAUSE --> WAIT[API 返回 hitl_pending=true]

    WAIT --> ADMIN[admin POST /hitl/resume]
    ADMIN --> RESUME[update_state + invoke None]
    RESUME --> CONTINUE[继续 rewrite→...→END]
```

</details>

---

## 七、层 5：工具层（Tools）

### 7.1 检索全流程（`tools/retriever.py`）

![检索全流程](./diagrams/14_retrieval.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    Q([query + user_roles]) --> MODE{RETRIEVAL_MODE}

    MODE -->|hybrid| HY[_hybrid_retrieve]
    MODE -->|dense| DE[_dense_retrieve]
    MODE -->|sparse| SP[_sparse_retrieve]

    subgraph HYBRID["Hybrid 混合检索"]
        H1[BM25 关键词召回] --> H3[加权融合 0.4/0.6]
        H2[Chroma 向量召回] --> H3
        H3 --> H4[doc_id 去重]
    end

    HY --> HYBRID
    DE -->|失败| SP
    SP -->|失败| DE

    HYBRID & DE & SP --> ACL[_acl_filter<br/>user_roles ∩ doc.acl_roles]

    ACL --> RER[rerank_docs Cross-Encoder]
    RER -->|失败| FB[keyword overlap fallback]

    FB --> KG{KG_ENABLED?}
    KG -->|是| KGQ[get_kg.query → to_context]
    KG -->|否| OUT
    KGQ --> OUT([docs + kg_context])
```

</details>

### 7.2 入库全流程（`tools/ingest.py`）

![入库全流程](./diagrams/15_ingest.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    START([ingest_files]) --> LOAD[load_documents<br/>PDF/TXT/MD/DOCX]
    LOAD --> META[metadata: source/doc_id/acl_roles/loaded_at]
    META --> SPLIT[split_documents 512/64]
    SPLIT --> VS[build_vectorstore → ChromaDB]
    VS --> BM25[set_chunks + persist_bm25.pkl]

    BM25 --> KG{KG_ENABLED?}
    KG -->|是| EXTRACT[ingest_chunks_to_kg]
    KG -->|否| DONE

    subgraph KG_PIPE["KG 抽取"]
        E1{KG_EXTRACTION_MODE}
        E1 -->|rule| E2[规则：书名号/规定/日期]
        E1 -->|llm| E3[LLM NER JSON 三元组]
        E1 -->|hybrid| E2 & E3
        E2 & E3 --> E4[去重 add_triple]
        E4 --> E5[save graph.pkl + graph.json]
    end

    EXTRACT --> KG_PIPE --> DONE([返回统计 dict])
```

</details>

### 7.3 冲突检测（`tools/conflict.py`）

![冲突检测](./diagrams/16_conflict.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    DOCS[检索到的 context_docs] --> GROUP[按 topic/首行分组]
    GROUP --> MULTI{同组 ≥2 条?}
    MULTI -->|否| SKIP[跳过]
    MULTI -->|是| DIFF{内容不同?}
    DIFF -->|否| SKIP
    DIFF -->|是| PRI[_meta_priority<br/>policy>faq, 新日期优先]
    PRI --> OUT[ConflictItem + resolution_hint]
    OUT --> FMT[format_conflicts 注入 Prompt]
```

</details>

### 7.4 知识图谱（`tools/knowledge_graph.py` + `kg_extractor.py`）

![知识图谱](./diagrams/17_knowledge_graph.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    INGEST([ingest chunk]) --> EXT[kg_extractor hybrid]
    EXT --> ADD[KnowledgeGraph.add_triple]
    ADD --> SAVE[pkl + json 持久化]

    QUERY([用户 question]) --> TOK[token 重叠打分]
    TOK --> SUB{中文子串匹配?}
    SUB --> TOP[top_k 三元组]
    TOP --> CTX[to_context 证据链文本]
    CTX --> PROMPT[注入 rag_prompt kg_context]
```

</details>

---

## 八、层 6：基础设施层

### 8.1 Provider 工厂 + 熔断

![Provider + 熔断](./diagrams/18_provider_circuit_breaker.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    CALL([get_chat_model / get_embeddings]) --> CB{Circuit Open?}
    CB -->|是| E503[ServiceUnavailableError]
    CB -->|否| PROV{LLM_PROVIDER / EMBEDDING_PROVIDER}

    PROV -->|ollama| OLL[ChatOllama / OllamaEmbeddings]
    PROV -->|openai| OAI[ChatOpenAI / OpenAIEmbeddings]

    OLL & OAI -->|成功| OK[record_success]
    OLL & OAI -->|失败| FAIL[record_failure]
    FAIL --> TH{failures ≥ 5?}
    TH -->|是| OPEN[熔断 OPEN 60s]
    TH -->|否| RAISE[抛出异常]
```

</details>

### 8.2 超时控制（`core/timeouts.py`）

![超时控制](./diagrams/19_timeouts.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart LR
    NODE[graph nodes _invoke_chain] --> TW[run_with_timeout ThreadPool]
    TW -->|≤ llm_timeout 30s| OK[返回 LLM 结果]
    TW -->|超时| E504[RAGTimeoutError → 节点兜底]
```

</details>

### 8.3 上下文压缩（`core/compression.py`）

![上下文压缩](./diagrams/20_compression.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TD
    MSG[chat_history] --> KEEP[保留 system + pin + 最近 N 轮]
    KEEP --> EST[估算 token]
    EST --> OVER{> max_tokens?}
    OVER -->|是| TRIM[丢弃最旧非 system 消息]
    OVER -->|否| OUT1[压缩后 history]

    CHUNKS[context_docs 按 rerank 序] --> BUDGET[trim_context_chunks<br/>RAG_CONTEXT_MAX_TOKENS=3000]
    BUDGET --> OUT2[拼接 context 字符串]
```

</details>

### 8.4 Docker 部署拓扑

![Docker 拓扑](./diagrams/21_docker_topology.png)

<details>
<summary>查看 Mermaid 源码（可编辑后运行 scripts/render_diagrams.py 重新出图）</summary>

```mermaid
flowchart TB
    USER[浏览器 / curl] --> UI[rag-ui :8501 Streamlit]
    USER --> API[rag-api :8000 FastAPI]

    API --> OLL[ollama :11434]
    API --> REDIS[redis :6379]
    API --> PG[postgres :5432 checkpoint]
    API --> VOL1[(chroma_db volume)]
    API --> VOL2[(kg_store volume)]
```

</details>

| Service | Port | Role |
|---------|------|------|
| rag-api | 8000 | FastAPI |
| rag-ui | 8501 | Streamlit |
| ollama | 11434 | LLM + Embed |
| redis | 6379 | Cache + rate limit |
| postgres | 5432 | HITL checkpoint |

---

## 九、API 端点速查

| 方法 | 路径 | 权限 | 对应流程 |
|------|------|------|----------|
| POST | `/auth/token` | 公开 | 层2 鉴权 |
| POST | `/chat` | chat | 层3 ask → 层4 全图 |
| POST | `/chat/stream` | chat | 层3 ask_stream |
| POST | `/hitl/resume` | admin | 层3 resume_hitl |
| POST | `/ingest` | admin/editor | 层5 入库 |
| GET | `/health` | 公开 | 存活探针 |
| GET | `/ready` | 公开 | Chroma + 熔断检查 |
| GET | `/stats` | health | BM25/KG/索引统计 |
| GET | `/metrics` | admin | 请求/缓存/HITL 计数 |

---

## 十、Eval 集成

```bash
# 默认评测 project_00
python eval/harness/run_eval.py --project 00 --prompt v1

# 对比 legacy project_01
python eval/harness/run_eval.py --project 01 --prompt v1

# 回归门禁
python eval/harness/run_eval.py --project 00 --prompt v2 --regression
```

---

## 十一、与 project_01 差异摘要

| 能力 | project_01 | project_00 |
|------|-----------|------------|
| Provider | 仅 Ollama | Ollama / OpenAI 可切换 |
| 鉴权 | 无 | JWT + RBAC |
| 缓存/限流 | 无 | Redis + 内存 fallback |
| BM25 | 内存，重启丢失 | pickle 持久化 + 启动重建 |
| KG | 无 | 规则 + LLM hybrid 抽取 |
| HITL | 无 | interrupt_before + Postgres |
| 冲突检测 | 无 | metadata 优先级 |
| guard 节点 | 无 | 安全门控 |
| ACL | 无 | chunk metadata acl_roles |

---

## 十二、一句话串起来（面试可背）

> **Client** 调 **API**（JWT + 限流）→ **agent** 压缩历史 + 查缓存 → **LangGraph**（guard → 可选 HITL 中断 → rewrite → **hybrid 检索 + ACL + KG + 冲突** → generate → grade 重试）→ **Provider** 调 LLM（带超时/熔断）→ 返回答案；**ingest** 走独立流水线写 Chroma + BM25 + KG。
