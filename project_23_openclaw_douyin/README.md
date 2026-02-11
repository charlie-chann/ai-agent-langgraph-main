# project_23_openclaw_douyin — 抖音视频脚本 Agent

## 商业价值

抖音日活超 7 亿，是全球用户量最大的短视频平台。创作者和品牌面临的核心痛点：
- **脚本构思难**：前 3 秒必须抓住眼球，否则用户直接滑走（跳出率超 80%）
- **内容节奏感弱**：视频缺乏 "hook → 内容 → CTA" 的完整结构
- **多种时长适配**：15s / 30s / 60s / 3min 不同时长的内容密度差异巨大

本 Agent 支持四种视频时长，自动生成包含"开场钩子 + 主体内容 + 结尾引导"的完整脚本，让创作者直接上手拍摄。

## 项目简介

抖音视频脚本 AI 生成 Agent，支持四种时长（15s/30s/60s/3min）、三种风格（知识干货/搞笑娱乐/励志正能量），自动合规检查。

## 技术架构

```
用户输入 (话题/关键词/时长/风格)
    ↓
content_generator.py  → 生成三段式脚本:
                         [开场钩子] 前3秒 (5种钩子模板)
                         [主体内容] 按时长动态调整密度
                         [结尾引导] CTA (点赞/评论/转发)
tag_optimizer.py       → 抖音话题标签库 (50+热门标签)
schedule_tool.py       → 发布时间 (晚19-23点流量高峰)
    ↓
agent.py (temperature=0.8) → 统一调度，高创意度
    ↓
app.py (Streamlit)     ← 脚本生成 / 标签优化 / 发布排期
api.py (FastAPI+SSE)   ← REST API
```

## 功能特性

- ✅ 四种视频时长：15s / 30s / 60s / 180s（自动时长对齐）
- ✅ 三种内容风格：知识干货 / 搞笑娱乐 / 励志正能量
- ✅ 5种开场钩子模板（悬念/对比/数字/共情/经验）
- ✅ 主体内容密度自适应（短视频精炼，长视频结构化）
- ✅ 结尾 CTA 按风格差异化（点赞 vs 评论 vs 转发）
- ✅ 抖音专属 16 个热门标签，最高 6 万+热度
- ✅ 高温度参数（0.8）强创意内容生成

## 运行说明

```bash
cd project_23_openclaw_douyin
uv run streamlit run app.py
# API:
uv run uvicorn api:app --port 8023 --reload
```

## API 接口

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | /health | - | 健康检查 |
| POST | /generate/script | topic, keywords, duration, style | 生成脚本 |
| POST | /tags | topic, keywords | 标签优化 |
| POST | /schedule | posts | 发布排期 |
| POST | /chat/stream | message | SSE 流式对话 |

## 测试

```bash
uv run pytest tests/ -v
# 30/30 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 15s脚本字数 | ~50字 |
| 60s脚本字数 | ~200字 |
| 180s脚本字数 | ~400字 |
| 合规率 | 100% |
| 测试通过率 | 30/30 (100%) |

## 后续改进

- [ ] 接入抖音热点话题 API，实时更新创作方向
- [ ] 添加 BGM 推荐（基于内容风格匹配）
- [ ] 支持竖屏分镜脚本（镜头切换建议）
- [ ] 接入 TTS 生成口播音频样本
