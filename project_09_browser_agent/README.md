# 🌐 Browser Automation Agent (project_09)

> 基于 LangGraph ReAct 循环的网页自动化智能体——无需真实浏览器即可抓取、搜索、提取网页内容，并自动生成结构化报告。

---

## 商业价值说明

### 解决的痛点
| 传统方式 | 本 Agent |
|---------|---------|
| 手动搜索 + 复制粘贴 | 自然语言指令一键完成 |
| 专业爬虫开发（数天） | 即配即用（分钟级） |
| 静态规则脚本，维护成本高 | LLM 动态理解任务，自适应 |
| 无法跨页面推理 | 多步 ReAct，跨页追踪信息 |

### 市场需求
- **市场研究**：竞品调研、行业动态收集
- **内容聚合**：新闻/博客定期抓取与摘要
- **数据收集**：招聘信息、价格监控、公告提取
- **自动化测试辅助**：页面内容验证

### 竞品分析
| 产品 | 优势 | 劣势 |
|------|------|------|
| Firecrawl | 专业爬取，JS渲染 | 付费API，无AI推理 |
| BrowserAgent (GPT) | 强大推理 | 依赖 OpenAI，数据外传 |
| Selenium/Playwright | 完全控制 | 需编程，无自然语言接口 |
| **本项目** | 本地部署，自然语言，无数据外传 | JS渲染需开启Playwright模式 |

---

## 技术架构

```
用户指令（自然语言）
       │
       ▼
  [task_parser] ── 指令清洗 / Prompt Injection 检测
       │
       ▼
  [LangGraph ReAct Loop]
  ┌────────────────────────────────────────┐
  │                                        │
  │  plan_and_act ──────► tools            │
  │      ▲                  │              │
  │      │    ToolMessage   │              │
  │      └──────────────────┘              │
  │           (max steps = 20)             │
  └────────────────────────────────────────┘
       │
       ▼
  [synthesize] ── LLM 综合原始内容 → 结构化报告
       │
       ▼
   Markdown 报告输出

工具集（browser_tool.py）：
  navigate_to       — HTTP GET + BeautifulSoup 解析
  get_page_text     — 全文提取
  extract_links     — 链接列表
  search_in_page    — 关键词段落搜索
  get_current_url   — 会话状态查询
  web_search_and_open — DuckDuckGo 搜索 + 打开首条
```

---

## 运行说明

### 环境准备

```bash
# 1. 确保 Ollama 运行
ollama serve
ollama pull qwen3.5:latest

# 2. 配置环境变量（可选）
cp .env.example .env

# 3. 安装依赖
uv pip install -r requirements.txt
```

### 启动 UI

```bash
cd project_09_browser_agent
uv run streamlit run app.py
```

### 启动 API

```bash
uv run python api.py
# 访问 http://localhost:8009/docs
```

### 运行测试

```bash
uv run pytest tests/ -v
```

---

## 功能演示

### 示例任务

```text
# 研究任务
搜索 Python LangChain 最新教程并总结要点

# 页面分析
访问 https://httpbin.org/json 并分析返回内容

# 链接提取
提取 https://example.com 的所有链接

# 关键词搜索
在 https://docs.python.org/3/ 中搜索 async 相关内容
```

### API 调用示例

```bash
# 同步执行
curl -X POST http://localhost:8009/task \
  -H "Content-Type: application/json" \
  -d '{"instruction": "搜索 Python 3.13 新特性"}'

# SSE 流式执行
curl -N http://localhost:8009/task/stream \
  -X POST -H "Content-Type: application/json" \
  -d '{"instruction": "访问 https://example.com 并总结"}'
```

---

## 安全规范

| 安全措施 | 实现方式 |
|---------|---------|
| Prompt Injection 检测 | `sanitize_instruction()` 正则过滤 |
| 私有地址封锁 | `_validate_url()` 拦截 localhost/192.168.x/10.x |
| URL 协议白名单 | 仅允许 http/https |
| 输入长度限制 | 最大 2000 字符 |
| 页面内容截断 | 防止超大页面导致 OOM |

---

## 评估结果

| 指标 | 值 |
|-----|----|
| 测试覆盖 | 24/24 ✅ |
| 工具调用 | 6个工具 |
| 平均响应时间 | ~15-30s（含网络+LLM） |
| 最大抓取步数 | 20步（可配置） |
| 支持页面类型 | 静态HTML（JS渲染需Playwright） |

---

## 后续改进方向

- [ ] 集成 Playwright 实现真实 JS 渲染（动态网站）
- [ ] 添加 `click_element` / `fill_form` 工具（表单自动化）
- [ ] 实现截图功能 + 视觉理解（多模态）
- [ ] 添加 Redis 缓存（相同URL 5分钟内复用）
- [ ] 支持定时监控任务（Celery/APScheduler）
- [ ] 添加 robots.txt 检查以符合爬虫礼仪
