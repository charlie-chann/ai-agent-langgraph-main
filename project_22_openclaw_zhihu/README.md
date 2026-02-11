# project_22_openclaw_zhihu — 知乎专业回答生成 Agent

## 商业价值

知乎是中国最大的知识问答社区，月活超 1 亿，用户偏向高学历、高收入群体。痛点：
- **撰写高质量回答耗时**：一篇 1000+ 字的专业回答通常需要 2-4 小时
- **结构化写作困难**：知乎用户对内容质量要求高，随意回答容易被折叠
- **专业度难以把握**：对不同用户群体（新手/从业者/专家）需要不同深度的表达

本 Agent 提供三种专业度档次（入门/中级/专家），自动生成结构化回答，包含结论先行、论点展开、案例支撑的完整框架。

## 项目简介

知乎问答 AI 生成 Agent，支持三种专业度的回答生成、标签优化和发布计划，温度参数优化为 0.4（专业内容低随机性）。

## 技术架构

```
用户输入 (问题/领域/专业度)
    ↓
content_generator.py  → 生成结构化回答 (STAR/框架/列表 等模式)
                         预估点赞数 (beginner:30 / intermediate:75 / expert:150)
tag_optimizer.py       → 知乎专属标签库 (职业发展/科技/投资等)
schedule_tool.py       → 知乎最佳发布时间 (午间+晚间深度阅读时段)
    ↓
agent.py (temperature=0.4) → 统一调度
    ↓
app.py (Streamlit)     ← UI
api.py (FastAPI+SSE)   ← REST API
```

## 功能特性

- ✅ 三种回答深度：入门分享 / 专业分析 / 深度洞见
- ✅ 自动生成点赞预估（帮助评估内容质量）
- ✅ 结构化写作（结论先行 → 背景分析 → 框架工具 → 误区 → 建议）
- ✅ 知乎专属 7 个领域标签库
- ✅ 低温度参数（0.4）确保内容专业、严谨
- ✅ 流式 AI 写作顾问

## 运行说明

```bash
cd project_22_openclaw_zhihu
uv run streamlit run app.py
# API:
uv run uvicorn api:app --port 8022 --reload
```

## API 接口

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | /health | - | 健康检查 |
| POST | /generate/answer | question, topic, expertise_level | 生成回答 |
| POST | /tags | topic, keywords | 标签优化 |
| POST | /schedule | posts | 发布排期 |
| POST | /chat/stream | message | SSE 流式对话 |

## 测试

```bash
uv run pytest tests/ -v
# 23/23 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 专家级回答字数 | 500-800字 |
| 内容合规率 | 100% |
| 测试通过率 | 23/23 (100%) |

## 后续改进

- [ ] 接入知乎热榜 API，自动发现热门问题
- [ ] 支持专栏文章生成（更长篇幅，含目录）
- [ ] 添加引用文献自动插入功能
- [ ] 基于历史点赞数据微调专业度参数
