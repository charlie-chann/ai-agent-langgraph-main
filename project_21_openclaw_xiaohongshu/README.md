# project_21_openclaw_xiaohongshu — 小红书图文笔记 Agent

## 商业价值

小红书月活超 2 亿，是中国最具影响力的内容种草平台。品牌营销人员和 KOL 面临的痛点：
- **图文笔记创作耗时**：构思标题 + 撰写正文 + 配图建议往往需要 1-2 小时
- **标题不够吸睛**：小红书用户滑动速度快，标题 3 秒决定是否点击
- **内容同质化**：大量相似内容造成审美疲劳，难以脱颖而出

本 Agent 支持三种笔记风格（生活方式/教程攻略/测评分享），自动生成配图建议，实现内容标准化批量产出。

## 项目简介

小红书图文笔记 AI 生成 Agent，支持标题优化、结构化正文、配图建议、标签推荐和发布排期。

## 技术架构

```
用户输入 (领域/关键词/风格)
    ↓
content_generator.py  → 生成图文笔记 (title + body + image_suggestions)
tag_optimizer.py       → 推荐小红书专属标签词库
schedule_tool.py       → 计算最佳发布时间 (午间 + 晚间女性用户活跃峰)
    ↓
agent.py              → 统一调度
    ↓
app.py (Streamlit)    ← UI: 笔记生成 / 标签优化 / 发布排期
api.py (FastAPI+SSE)  ← REST API
```

## 功能特性

- ✅ 三种笔记风格：lifestyle（生活方式）/ tutorial（教程）/ review（测评）
- ✅ 自动生成配图拍摄建议（减少创作者构思成本）
- ✅ 小红书专属标签词库（好物推荐/种草/护肤等 20+ 标签）
- ✅ 合规检查（违禁词过滤）
- ✅ 智能发布排期（午间 12-13 点，晚间 20-23 点）
- ✅ AI 运营顾问（流式对话）

## 运行说明

```bash
cd project_21_openclaw_xiaohongshu
uv run streamlit run app.py
# API:
uv run uvicorn api:app --port 8021 --reload
```

## API 接口

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | /health | - | 健康检查 |
| POST | /generate | topic, keywords, style | 生成笔记 |
| POST | /tags | topic, keywords | 标签优化 |
| POST | /schedule | posts | 发布排期 |
| POST | /chat/stream | message | SSE 流式对话 |

## 测试

```bash
uv run pytest tests/ -v
# 27/27 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 笔记生成P99延迟 | < 50ms |
| 标题长度合规率 | 100% |
| 测试通过率 | 27/27 (100%) |

## 后续改进

- [ ] 接入小红书开放平台 API，实时拉取热门笔记分析
- [ ] 添加封面图 AI 生成（DALL-E / Stable Diffusion）
- [ ] 支持多语言（面向出海小红书场景）
- [ ] A/B 测试不同标题风格的点击率
