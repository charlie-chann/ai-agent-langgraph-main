# 🔬 Project 04 — Deep Research Agent

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
咨询公司、投行、PE、Market Intelligence 团队需要大量行业研究报告，
传统方式：1-2 名分析师花 2-3 天做初稿。本 Agent 将初稿时间压缩到 5-10 分钟。

**目标用户**：
- 咨询公司（McKinsey/Bain 风格快速行业扫描）
- 风险投资（行业尽调报告）
- 企业战略部门（竞争对手分析）
- 市场情报 SaaS（Crayon/Klue 类产品核心能力）

**与 OpenAI Deep Research 对比**：
- 本地运行，数据不出企业网络
- 自定义迭代轮次和覆盖度阈值
- 可接入内部数据库（RAG 扩展）

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| OpenAI Deep Research | 质量高 | 数据上云，$200/月 |
| Perplexity Pro | 实时搜索 | 不可定制，数据外传 |
| Elicit | 学术聚焦 | 非通用 |
| **本项目** | 本地运行，可定制，免费 | 需要本地算力 |

---

## 项目简介
基于 LangGraph 的迭代式深度研究 Agent，自动执行多轮搜索→合成→缺口分析→补充搜索，
直到覆盖度达标（默认 80%）或轮次上限（默认 4 轮），最终生成专业研究报告。

---

## 技术架构

```
研究主题
    │
    ▼
┌──────────────────┐
│ 🎯 Query Generator│ → N 个多角度搜索词（背景/现状/数据/趋势）
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  🔍 Web Searcher  │ → DuckDuckGo × N 并行搜索
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   📖 Synthesizer  │ → 合并新旧研究笔记，去重，整理主题
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  🕵️ Gap Analyzer  │ → coverage_score (0-1), gaps[], followup_queries[]
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
score<0.8  score≥0.8 or max_rounds
    │         │
    ▼         ▼
(loop)  ┌──────────────────┐
        │  ✍️ Report Writer │ → Comprehensive markdown report
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │  ✨ Polisher      │ → Add TL;DR, fix gaps, professional tone
        └────────┬─────────┘
                 │
                 ▼
            Final Report + Auto-save
```

---

## 环境配置

```bash
cd project_04_deep_research
uv pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3.5:latest
```

## 启动命令

```bash
# UI
uv run streamlit run app.py

# API
uv run uvicorn api:app --reload --port 8004

# Tests
uv run pytest tests/ -v
```

---

## 评估结果

| 指标 | 数值 |
|------|------|
| 平均完整研究时间（4轮）| ~90s |
| 平均报告字数 | ~2000字 |
| Coverage Score（人工验证）| 76% 达到 0.8+ |
| 报告质量满意度（10 题）| 80% |

---

## 后续改进方向
- [ ] 接入 PDF 全文阅读（论文、报告摘入）
- [ ] 并行搜索（asyncio）提升速度
- [ ] 图表生成（matplotlib / plotly）
- [ ] DOCX / PDF 输出格式
- [ ] 集成 Arxiv / Wikipedia 专项搜索
- [ ] 多语言报告（英/中双语）
