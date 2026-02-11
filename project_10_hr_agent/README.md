# 👔 HR Recruitment Screening Agent (project_10)

> AI 驱动的招聘筛选系统——多维度评分算法 + LangGraph 对话助手，公平、高效、可解释地处理批量简历筛选。

---

## 商业价值说明

### 解决的痛点
| 传统方式 | 本 Agent |
|---------|---------|
| HR手动逐份阅读简历（每份5-10分钟） | 批量自动评分（秒级） |
| 评分标准因人而异，主观偏见 | 加权多维度算法，透明可审计 |
| 无法快速提取候选人关键技能 | 关键词匹配+原文搜索双重验证 |
| 面试题依赖 HR 个人经验 | 基于岗位+候选人背景生成个性化题目 |

### 市场规模
- 全球招聘软件市场 2024 年约 **330 亿美元**，年增长 7%
- 企业平均每笔招聘耗时 **23-42 天**，本工具可压缩筛选阶段至 1-2 天
- 适用场景：中大型企业 HR 部门、猎头公司、校园招聘

### 竞品分析
| 产品 | 特点 | 不足 |
|------|------|------|
| HireVue | AI 视频面试 | 昂贵，数据外传 |
| Greenhouse ATS | 全流程管理 | 无智能筛选 |
| ChatGPT/Claude | 灵活对话 | 无结构化评分，无CRUD |
| **本项目** | 本地部署，量化评分，对话+批处理双模式 | 需与ATS系统集成 |

---

## 技术架构

```
用户输入（简历JSON / 对话指令）
       │
       ├── 批量筛选模式
       │     │
       │     ▼
       │   [resume_scorer.py]
       │     ├── 技能匹配 (50%) ── 关键词 + raw_text 双重搜索
       │     ├── 工作年限 (25%) ── 线性分段评分
       │     ├── 学历要求 (15%) ── 学历等级映射
       │     └── 稳定性   (10%) ── 平均任职时长
       │     │
       │     ▼
       │   ScoringResult → 决策: shortlist / review / reject
       │     │
       │     ▼
       │   [report_tool.py] → Markdown 招聘报告
       │
       └── 对话助手模式
             │
             ▼
           [LangGraph ReAct Loop]
           hr_agent ──► tools ──► hr_agent ──► END
             │
             tools:
             ├── add_candidate / get_candidate / list_candidates
             ├── update_candidate_status / set_candidate_score
             └── generate_screening_report / list_reports
```

---

## 运行说明

### 环境准备

```bash
# 1. 确保 Ollama 运行
ollama serve
ollama pull qwen3.5:latest

# 2. 配置环境变量
cp .env.example .env

# 3. 安装依赖
uv pip install -r requirements.txt
```

### 启动 UI

```bash
cd project_10_hr_agent
uv run streamlit run app.py
```

### 启动 API

```bash
uv run python api.py
# 访问 http://localhost:8010/docs
```

### 运行测试

```bash
uv run pytest tests/ -v
```

---

## 评分算法详解

```
total_score = skill_score * 0.50
            + experience_score * 0.25
            + education_score * 0.15
            + stability_score * 0.10

决策规则：
  >= 0.65 → shortlist (入围，建议安排面试)
  <= 0.35 → reject    (淘汰，不符合基本要求)
  其他    → review    (待定，需 HR 人工确认)
```

---

## API 调用示例

```bash
# 批量筛选
curl -X POST http://localhost:8010/screen \
  -H "Content-Type: application/json" \
  -d '{
    "job": {
      "title": "Python工程师",
      "required_skills": ["Python", "FastAPI"],
      "min_years_exp": 3
    },
    "resumes": [
      {"id": "R1", "name": "张伟", "skills": ["Python", "FastAPI", "Docker"],
       "years_experience": 5, "education": "本科", "job_count": 2}
    ]
  }'

# 对话助手
curl -X POST http://localhost:8010/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我列出所有已入围的Python工程师候选人"}'
```

---

## 评估结果

| 指标 | 值 |
|-----|----|
| 测试覆盖 | 22/22 ✅ |
| 评分维度 | 4维（技能/经验/学历/稳定性） |
| 批量处理能力 | 50份/批（可配置） |
| 单份简历评分时间 | < 5ms（纯算法，无LLM） |
| 对话响应时间 | ~5-15s（含 Ollama 推理） |

---

## 后续改进方向

- [ ] 集成 LLM 语义理解（当前为关键词匹配，可升级为向量相似度）
- [ ] 添加简历 PDF/Word 解析（`python-docx`, `pdfminer.six`）
- [ ] 支持 ATS 系统集成（Greenhouse/BambooHR API）
- [ ] 添加候选人黑白名单功能
- [ ] 实现面试安排日历集成
- [ ] 增加偏见检测报告（分析是否有学历/名校偏好）
