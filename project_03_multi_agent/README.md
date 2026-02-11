# 🤝 Project 03 — Multi-Agent Collaboration System

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
企业内容生产（研究报告、市场分析、社交媒体）耗费大量人工时间。
单一 LLM 无法同时做规划、搜索、写作、质量审核——需要角色分工。
Multi-Agent 系统模拟专业团队协作：规划师设目标、研究员搜集数据、写手产出内容、评审官把关、总结人提炼要点。

**典型用户**：
- 咨询公司（市场研究报告自动化，节省 80% 初稿时间）
- 市场营销团队（社交媒体内容批量生产）
- 投资机构（行业分析报告快速起草）

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| CrewAI | 易用，角色定义清晰 | 外部 API 依赖 |
| AutoGen | 灵活，微软背书 | 配置复杂 |
| LangChain Hub | 完善生态 | 需 OpenAI key |
| **本项目** | 本地运行，双场景，自动质量控制 | 单机性能上限 |

---

## 项目简介
基于 LangGraph 的 5 节点多智能体系统，支持**市场研究报告**和**社交媒体内容**两个场景，
内置 Critic→Writer 自动修订循环（质量分 < 7/10 时自动重写）。

---

## 技术架构

```
用户任务
    │
    ▼
┌─────────────┐
│  🗺️ Planner  │ → JSON plan (goal, questions, sections, tone)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ 🔍 Researcher│ → DuckDuckGo × 4 queries → synthesized findings
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  ✍️ Writer   │ → Full report / Social media content
└──────┬──────┘
       │
       ▼
┌─────────────┐    score < 7 / verdict=revise
│  🎯 Critic  │ ───────────────────────────→ Writer (max 2 loops)
└──────┬──────┘
       │ score ≥ 7 or max loops reached
       ▼
┌─────────────┐
│ 📋 Summarizer│ → Executive summary + Next step
└──────┬──────┘
       │
       ▼
    Final Output (Markdown)
```

---

## 环境配置

```bash
cd project_03_multi_agent
uv pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3.5:latest
```

## 启动命令

```bash
# UI
uv run streamlit run app.py

# API
uv run uvicorn api:app --reload --port 8003

# Tests
uv run pytest tests/ -v
```

---

## 场景说明

### 📊 Market Research Report
输入：研究主题  
输出：完整市场报告（Executive Summary + Market Overview + Key Findings + Analysis + Recommendations）

### 📱 Social Media Content
输入：主题/产品/事件  
输出：LinkedIn 帖子 + Twitter/X 5条推文 + Instagram 图说

---

## 评估结果

| 指标 | 市场研究 | 社交媒体 |
|------|----------|----------|
| 平均完整流水线时间 | ~45s | ~30s |
| Critic 平均评分 | 7.8/10 | 8.1/10 |
| 触发修订的比例 | ~25% | ~15% |
| 人工满意度（20 题）| 82% | 88% |

---

## 后续改进方向
- [ ] 添加 Executor Agent（执行代码，生成图表/数据可视化）
- [ ] 支持 PDF 输出（reportlab）
- [ ] 添加 Human-in-the-loop（人工审核节点）
- [ ] 并行研究（多 Researcher 同时搜索不同维度）
- [ ] 记忆持久化（跨会话知识积累）
