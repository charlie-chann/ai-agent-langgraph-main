# AI Agent 工程实战合集 🤖

> 基于 LangGraph + LangChain + Ollama 的生产级 AI Agent 项目集，共 **30 个独立可运行项目**，全部测试通过。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| LLM 底座 | Ollama + qwen2.5:1.5b（本地，数据不外传） |
| Agent 框架 | LangChain v1.x + LangGraph |
| UI | Streamlit |
| API | FastAPI + SSE 流输出 |
| 包管理 | uv |
| Python | 3.11+ |

---

## 项目总览

### 核心 Agent（P0-P2）

| # | 项目 | 优先级 | 测试 | 核心特性 |
|---|------|--------|------|---------|
| 01 | [RAG Agent](project_01_rag_agent/) | P0 ✅ | 3/3 | Agentic RAG, 混合检索, 引用溯源 |
| 02 | [Tool Agent](project_02_tool_agent/) | P0 ✅ | 6/6 | ReAct 6工具, 安全沙箱 |
| 03 | [Multi Agent](project_03_multi_agent/) | P0 ✅ | 5/5 | LangGraph 多节点协作 |
| 04 | [Deep Research](project_04_deep_research/) | P0 ✅ | 7/7 | 迭代搜索+报告生成 |
| 05 | [Enterprise Bot](project_05_enterprise_bot/) | P1 ✅ | 11/11 | RBAC+工单+知识库 |
| 06 | [Code Agent](project_06_code_agent/) | P1 ✅ | 15/15 | 安全代码执行+Lint |
| 07 | [Finance Agent](project_07_finance_agent/) | P1 ✅ | 17/17 | DCF+合规+组合分析 |
| 08 | [Customer Service](project_08_customer_service/) | P1 ✅ | 23/23 | 情绪分析+全链路客服 |
| 09 | [Browser Agent](project_09_browser_agent/) | P2 ✅ | 24/24 | 网页抓取+ReAct自动化 |
| 10 | [HR Agent](project_10_hr_agent/) | P2 ✅ | 22/22 | 多维简历评分+候选人CRUD |

### 垂直行业 Agent

| # | 项目 | 方向 | 测试 | 核心特性 |
|---|------|------|------|---------|
| 11 | [Legal Agent](project_11_legal_agent/) | 法律合规 ✅ | ✅ | 合同分析, 法律条文检索 |
| 12 | [Quant Agent](project_12_quant_agent/) | 量化金融 ✅ | 29/29 | 技术指标, DCF, 夏普比率, VaR |
| 13 | [Medical Agent](project_13_medical_agent/) | 医疗健康 ✅ | 29/29 | 症状分诊, 预约管理, EHR摘要 |
| 14 | [Sales CRM Agent](project_14_sales_crm_agent/) | 销售 ✅ | 31/31 | 线索评分, 邮件生成, CRM |
| 15 | [Supply Chain Agent](project_15_supply_chain_agent/) | 供应链 ✅ | 18/18 | 库存优化, TSP路径规划 |
| 16 | [Education Agent](project_16_education_agent/) | 教育 ✅ | 13/13 | 自适应学习计划, 测验生成 |
| 17 | [Ops Agent](project_17_ops_agent/) | 运维 ✅ | 13/13 | 日志分析, 根因定位, 工单 |
| 18 | [Ecommerce Agent](project_18_ecommerce_agent/) | 电商 ✅ | 13/13 | 竞品监控, 定价建议 |
| 19 | [Privacy Agent](project_19_privacy_agent/) | 数据安全 ✅ | 15/15 | PII检测/脱敏, 合规审计 |

### openclaw 社媒内容系列

| # | 项目 | 平台 | 测试 | 核心特性 |
|---|------|------|------|---------|
| 20 | [openclaw 微博](project_20_openclaw_weibo/) | 微博 ✅ | 20/20 | 内容生成, 话题优化, 发布排期 |
| 21 | [openclaw 小红书](project_21_openclaw_xiaohongshu/) | 小红书 ✅ | 27/27 | 图文笔记, 配图建议, 三种风格 |
| 22 | [openclaw 知乎](project_22_openclaw_zhihu/) | 知乎 ✅ | 23/23 | 专业回答, 三段式结构, 深度内容 |
| 23 | [openclaw 抖音](project_23_openclaw_douyin/) | 抖音 ✅ | 30/30 | 视频脚本, 开场钩子, CTA设计 |
| 24 | [openclaw Twitter](project_24_openclaw_twitter/) | Twitter/X ✅ | 35/35 | 推文/线程, <=280字符, UTC排期 |

### openclaw 智能工作流系列

| # | 项目 | 功能 | 测试 | 核心特性 |
|---|------|------|------|---------|
| 25 | [openclaw 早报](project_25_openclaw_morning_brief/) | 信息聚合 ✅ | 44/44 | RSS多源聚合, 去重排序, 分类早报 |
| 26 | [openclaw 深度调研](project_26_openclaw_deep_research/) | 研究分析 ✅ | 49/49 | 子查询分解, 交叉验证, 可信度评分 |
| 27 | [openclaw 热点追踪](project_27_openclaw_trend_tracker/) | 趋势监控 ✅ | 54/54 | 热度衰减模型, 内容机会分析 |
| 28 | [openclaw 内容改写](project_28_openclaw_content_repurposer/) | 内容分发 ✅ | 63/63 | 5平台适配, 合规检查, 字符限制 |
| 29 | [openclaw 个人记忆](project_29_openclaw_personal_memory/) | 知识管理 ✅ | 57/57 | 7种记忆类型, 关键词召回, 重要度分级 |
| 30 | [openclaw 营销规划](project_30_openclaw_campaign_planner/) | 营销自动化 ✅ | 55/55 | 5种活动类型, 90天日历, 触达预估 |

---

## 快速启动

```bash
# 1. 启动 Ollama
ollama serve && ollama pull qwen2.5:1.5b

# 2. 检查环境
uv run python scripts/check_ollama.py

# 3. 运行任意项目（Streamlit UI）
cd project_01_rag_agent
uv run streamlit run app.py
补充优化：
1.uv pip install -r requirements.txt
2.uv run streamlit run app.py

# 4. 启动 API 服务
uv run uvicorn api:app --port 8000 --reload
```

---

## 目录结构

```
ai_agent_dev/
├── plan001.md                       # 项目规划文档
├── scripts/                         # 公共工具脚本
│   ├── check_ollama.py
│   ├── setup_env.py
│   ├── benchmark.py
│   └── run_all.bat
├── project_01_rag_agent/ ... project_19_privacy_agent/        # 垂直行业 Agent
├── project_20_openclaw_weibo/ ... project_24_openclaw_twitter/ # 社媒内容系列
└── project_25_openclaw_morning_brief/ ... project_30_openclaw_campaign_planner/ # 智能工作流系列
```

---

## 运行所有测试（PowerShell）

```powershell
Get-ChildItem -Directory -Filter "project_*" | ForEach-Object {
    if (Test-Path "/tests/") {
        Write-Host "Testing ..."
        uv run pytest "/tests/" -q --tb=no
    }
}
```
