# project_00_rag_agent — 给运维的部署说明（测试 / 生产）

> 开发交付物：本仓库代码 + 本说明。密钥不要进 Git，由运维在服务器/配置中心注入。

---

## 一、服务是什么

- **名称**：Production RAG Agent（`project_00_rag_agent`）
- **给谁用**：公司 Java 服务通过 HTTP 调用（登录拿 Token → 会话 → chat）
- **技术**：Python FastAPI +（可选）Streamlit UI；依赖 Ollama 或云大模型、Redis、Postgres；向量库为本地 Chroma 目录

---

## 二、发版约定（开发会告知）

| 项 | 说明 |
|----|------|
| 仓库路径 | `project_00_rag_agent/` |
| 发版标识 | 分支名或 Git tag（例：`test-2026xxxx` / `v1.0.0`） |
| 环境 | 测试：`APP_ENV=test`；生产：`APP_ENV=prod`（**两套独立部署，数据与密钥隔离**） |

---

## 三、推荐部署方式（Docker Compose）

在服务器上进入目录后：

```bash
cd project_00_rag_agent

# 1. 准备环境配置（勿提交真实密钥到 Git）
# 测试：cp .env.test.example .env.test   后由运维填写真实值
# 生产：cp .env.prod.example .env.prod   后由运维填写真实值
export APP_ENV=test          # 生产改为 prod

# 2. 启动（含 ollama / redis / postgres / api / ui）
docker compose up -d --build

# 3. 拉取本地模型（若 LLM_PROVIDER=ollama）
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull nomic-embed-text
```

若公司规定用镜像仓库：开发打 tag 后 CI 构建镜像，运维只 `docker pull` + 按同等环境变量启动即可（镜像内默认入口：`uvicorn main:app --host 0.0.0.0 --port 8000`）。

---

## 四、必须配置的环境变量（摘要）

| 变量 | 测试 | 生产 | 说明 |
|------|------|------|------|
| `APP_ENV` | `test` | `prod` | 环境标识；prod 下弱 `JWT_SECRET` 会启动失败 |
| `JWT_SECRET` | 测试专用密钥（≥32 位） | **强随机密钥，勿与测试相同** | 签发 Bearer Token |
| `DEMO_USERS_JSON` | 测试账号 | 生产强密码账号 | Java 调 `/auth/token` 用 |
| `DATABASE_URL` | 测试库 | 生产库 | 会话 / checkpoint |
| `REDIS_URL` | 测试 Redis | 生产 Redis | 缓存与限流 |
| `OLLAMA_BASE_URL` 或云 API | 按实际 | 按实际 | 大模型地址 |
| `API_BASE_URL` | 测试对外域名 | 生产对外域名 | 给 Java / UI 用的对外地址 |
| `CHECKPOINTER_BACKEND` | 建议 `postgres` | 必须 `postgres` | 勿用 memory 上生产 |
| `CONVERSATIONS_BACKEND` | 建议 `postgres` | 必须 `postgres` | 同上 |

完整示例见：`.env.test.example`、`.env.prod.example`。

---

## 五、端口与探活

| 用途 | 端口 | 路径 |
|------|------|------|
| API（给 Java） | **8000** | 文档：`/docs` |
| 健康检查 | 8000 | `GET /health` → 应含 `"status":"ok"`、`"app_env":"test|prod"` |
| 就绪检查 | 8000 | `GET /ready` |
| UI（可选） | 8501 | Streamlit；可不对公网开放 |

对外建议只暴露 **HTTPS 域名 → 8000**（公司 Nginx / 网关）。  
**不要**把 5432、6379、11434 暴露到公网。

---

## 六、持久化（重要）

下列目录/卷需持久化，否则重启或重建容器会丢知识库/上传文件：

- `chroma_db/` — 向量库数据（**不会**随 Git 代码自动带上；空库需业务方 ingest，或另行拷贝已有目录）
- `kg_store/` — 知识图谱数据
- Postgres / Redis 数据卷
- 上传临时目录（compose 中有 `rag_uploads` volume）

---

## 七、给 Java 的联调信息（部署完成后回传开发）

部署成功后请提供：

1. **baseUrl**（例：`https://rag-test.公司.com`）
2. 确认 `curl -s https://…/health` 正常
3. 测试/生产账号由开发或安全侧另行下发（对应 `DEMO_USERS_JSON`）

Java 主要调用：

1. `POST /auth/token` — 换 Bearer Token  
2. `POST /conversations` — 创建会话  
3. `POST /conversations/{id}/chat` — 对话（超时建议 60～120s）

---

## 八、回滚

1. 切换到上一 Git tag / 上一镜像版本  
2. `docker compose up -d`（或公司发布平台回滚）  
3. **不要**用测试库/测试密钥回滚到生产；数据卷回滚需单独评估

---

## 九、常见问题

| 现象 | 处理 |
|------|------|
| `/health` 不通 | 看 `rag-api` 日志；检查 8000 与网关转发 |
| 能登录但问答失败 | 查 Ollama/云 API、模型是否已 pull |
| 知识库没内容 | `chroma_db` 为空：需 ingest 或拷贝数据目录 |
| `APP_ENV=prod` 起不来 | 检查 `JWT_SECRET` 是否仍为示例弱密钥或过短 |

---

## 十、联系人

- 开发对接：___________（姓名 / 群）
- 发版版本：___________（分支或 tag）
- 目标环境：□ 测试　□ 生产
- 计划上线时间：___________

（开发填写后发给运维即可。）
