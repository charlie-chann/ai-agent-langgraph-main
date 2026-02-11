# Project 07 — Finance / Compliance Analysis Agent

> Production-grade AI stock analyst and portfolio compliance tool — real market data, zero cloud dependency.

---

## 商业价值说明书

### 市场需求与痛点

| 痛点 | 现有方案的不足 | 本项目解法 |
|------|--------------|-----------|
| 研报生产成本高 | 1份分析报告需分析师耗时数小时 | AI在30秒内生成结构化分析报告 |
| 合规检查人工滞后 | 基金经理手动核查持仓限额，易漏检 | 自动化合规引擎，实时扫描，违规即报警 |
| 量化数据获取门槛高 | Bloomberg终端 $25,000+/年 | yfinance完全免费，覆盖全球主要市场 |
| 数据泄露风险 | OpenAI/Claude API将财务数据发送到境外 | 全本地 Ollama，数据不离开内网 |
| 中小机构缺乏合规工具 | 专业合规系统定制费用几十万 | 开源，可配置规则，立即部署 |

**目标客户**: 中小私募基金、资产管理公司内研团队、个人专业投资者

**市场规模**: 全球金融数据与分析软件市场 2024 年约 $130 亿，中国金融科技市场年增长率 >20%。

### 竞品分析

| 产品 | 优势 | 劣势 |
|------|------|------|
| Bloomberg Terminal | 数据最全、实时 | $25,000+/年，无AI生成分析 |
| Wind 万得 | A股数据最权威 | 高昂授权费，无本地AI |
| ChatGPT + 插件 | LLM能力强 | 数据需手动输入，实时性差，境外服务器 |
| Perplexity Finance | 搜索整合好 | 无法做合规计算，无本地化 |
| **本项目** | **本地+实时数据+合规引擎+免费** | 依赖本地GPU/CPU运行LLM |

---

## 项目简介

Finance Agent 是一个基于 LangChain ReAct + 本地 Ollama LLM 的金融分析智能体，集成 yfinance 实时数据、DCF估值模型、多维度基本面评分、投资组合合规筛查和新闻分析功能。全程本地运行，无数据外传。

---

## 技术架构

```
┌─────────────────────────────────────────────┐
│    Streamlit UI (4 modes) / FastAPI SSE      │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │   ReAct Agent      │  ← qwen3.5:latest (Ollama)
         │   15 Tools         │
         └──────┬─────────────┘
                │
   ┌────────────┼─────────────────┬────────────────┐
   ▼            ▼                 ▼                ▼
market_data  news_tool       analysis_tool   compliance_tool
(yfinance)  (DuckDuckGo)    (Pure Python)    (Rule Engine)
   │            │                 │                │
Real prices  Headlines        DCF / Scores   Position Limits
Financials   Sector News     Portfolio Risk   ESG Flags
```

---

## 运行说明

### 前置条件
```bash
ollama serve
ollama pull qwen3.5:latest
```

### 安装依赖
```bash
cd project_07_finance_agent
pip install yfinance pandas plotly  # or uv add
```

### 启动 Streamlit UI
```bash
cp .env.example .env
uv run streamlit run app.py
```
访问 http://localhost:8501

### 启动 API 服务
```bash
uv run python api.py
```
API 文档: http://localhost:8007/docs

### 运行测试
```bash
uv run pytest tests/ -v
```

---

## 功能说明

### 模式 1：Research Chat（AI对话分析）
```
User: Analyse Apple (AAPL) — give me a full fundamental analysis

Agent:
[get_stock_quote] → Price: $182.50, P/E: 28.4, Beta: 1.2...
[get_financials] → Revenue: $383B, Net Margin: 25.3%, ROE: 145%...
[get_price_history] → MA50 trend: Bullish, Vol: 24.5%...
[analyse_fundamentals] → Score: 7/9 (78%) — Rating: Buy
Final Answer: AAPL shows strong fundamentals...
```

### 模式 2：Quick Quote（快速行情）
- 实时价格 + 52周高低
- Plotly K线图（1个月−2年）
- 财务摘要指标

### 模式 3：Compliance Check（合规审查）
- 粘贴JSON格式持仓
- 实时扫描持仓集中度、行业集中度、ESG违规
- 返回 ✅/⚠️/❌ 报告

### 模式 4：Reports（研报管理）
- 列出所有AI生成的研报
- 支持在线阅读Markdown报告

---

## 评估结果

| 指标 | 值 |
|------|-----|
| 单元测试通过率 | 17/17 (100%) |
| 合规规则准确率 | 4/4 规则 100% 正确 |
| DCF计算误差 | <0.1%（对比手动计算）|
| 平均响应延迟（完整分析）| ~18s（CPU，qwen3.5:latest）|

详见 [docs/evaluation.md](docs/evaluation.md)

---

## 免责声明

本系统仅供信息参考和教育目的，不构成任何投资建议或金融咨询。所有数据来源于公开信息（yfinance）。投资决策请咨询持牌金融顾问。

---

## 后续改进方向

- [ ] PDF报告导出（含图表）
- [ ] A股支持（东方财富/akshare数据源）
- [ ] 期权数据 + 隐含波动率分析
- [ ] 组合回测（历史收益率 vs 基准）
- [ ] 实时合规违规Webhook告警
- [ ] 集成 project_01 RAG 用于分析招股说明书/年报PDF
