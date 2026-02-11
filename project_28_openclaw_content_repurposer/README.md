# ✍️ Project 28 - OpenClaw 内容改写 Agent

## 商业价值说明

### 解决的痛点
- 一稿多用难：同一内容在微博、小红书、知乎格式规则完全不同，手工改写极耗时
- 违规风险高：不同平台对敏感词、广告词、字数限制各有要求，容易踩雷
- 人力成本贵：MCN 机构雇专职运营多平台改写，月薪 8K-15K
- 发布效率低：同一创意内容，适配 5 个平台往往需要 2-4 小时

### 市场需求
- 中国 MCN 机构超 3 万家，每天产出内容超过 1 亿条
- 内容营销 SaaS 市场 2024 年超 120 亿元人民币
- 品牌内容团队平均在"格式适配"上浪费 30% 工时

### 竞品分析
| 产品 | 优势 | 劣势 |
|------|------|------|
| 新媒体管家 | 一键发布多平台 | 无 AI 改写，只分发 |
| 万词王 | 批量文章生成 | 质量差，重复率高 |
| Copy.ai | 英文内容改写强 | 中文支持差 |
| **本项目** | 平台规则感知 + 合规检查 + 本地 AI | 依赖本地 Ollama |

---

## 项目简介

一键将内容改写适配微博、小红书、知乎、抖音、Twitter 等平台，自动校验字数限制、添加话题标签，内置合规检查功能。

---

## 技术架构

```
原始内容 + 话题
      │
      ▼
tools/content_adapter.py
┌─────────────────────────────────────────────────┐
│  get_platform_specs(platform)                   │  ← 获取平台规格
│  adapt_for_platform(content, topic, platform)   │  ← 单平台适配
│  adapt_for_all_platforms(content, topic)        │  ← 全平台批量
│  check_compliance(content, platform)            │  ← 合规检查
└────────────────────────┬────────────────────────┘
                         │ PlatformContent
                         ▼
              agent.py ─ run_repurpose()
                       ─ run_compliance_check()
                       ─ run_get_platform_specs()
                  ├── app.py  (Streamlit  :8501)
                  └── api.py  (FastAPI    :8028)

平台约束:
  微博    → 140 字，话题标签 #xxx#
  小红书  → 1000 字，表情符号，关键词标签
  知乎    → 8000 字，结构化回答格式
  抖音    → 1000 字，BGM 建议，话题挑战
  Twitter → 280 字，英文优化，#hashtag
```

---

## 运行说明

```bash
cd project_28_openclaw_content_repurposer
uv pip install -r requirements.txt

uv run streamlit run app.py
uv run uvicorn api:app --host 0.0.0.0 --port 8028
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 + 支持的平台 |
| POST | `/content/repurpose` | 一键多平台改写 |
| POST | `/content/repurpose/{platform}` | 指定单平台改写 |
| GET | `/platform/specs` | 获取平台规格参数 |
| POST | `/compliance/check` | 内容合规检查 |
| GET | `/chat/stream` | SSE 流式对话 |

### 示例
```bash
# 一键改写
curl -X POST http://localhost:8028/content/repurpose \
  -H "Content-Type: application/json" \
  -d '{
    "content": "我们发布了新版 AI 产品，支持多模态输入...",
    "topic": "AI产品发布",
    "platforms": ["微博", "小红书", "知乎"]
  }'

# 合规检查
curl -X POST http://localhost:8028/compliance/check \
  -H "Content-Type: application/json" \
  -d '{"content": "买它绝对最好用！", "platform": "小红书"}'
```

---

## 评估结果

| 指标 | 数值 |
|------|------|
| 单平台适配耗时 | < 100ms |
| 5 平台批量改写 | < 300ms |
| 字数合规率 | 100%（硬性截断） |
| 合规检查规则数 | 每平台 5-8 条 |
| 测试覆盖率 | 63 个测试，100% 通过 |

---

## OpenClaw 技能集成

- **content-publisher**: 多平台内容发布规则引擎
- **content-organizer**: 内容结构化与格式转换
- **content-summarizer**: 内容摘要与压缩（适配字数限制）

---

## 后续改进方向

- [ ] 接入平台 API 直接发布（微博/小红书/Twitter API）
- [ ] AI 改写质量评分（语义相似度保留率）
- [ ] 违禁词库实时更新
- [ ] 图片生成建议（配套 DALL·E/Stable Diffusion）
- [ ] A/B 测试版本生成（同一内容生成多个变体）
- [ ] 与 P27 热点追踪联动，热点来了自动触发改写
