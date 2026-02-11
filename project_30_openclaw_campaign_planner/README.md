# 📣 Project 30 - OpenClaw 营销活动规划 Agent

## 商业价值说明

### 解决的痛点
- 营销计划制定耗时：从策划到内容日历，人工通常需要 1-3 天
- 多平台协调复杂：不同平台的发布节奏、内容类型完全不同
- 新手不懂方法论：中小企业、个人创业者缺乏专业营销知识
- 预算浪费：不知道如何分配触达量最大化

### 市场需求
- 中国中小企业数量超 5000 万，普遍缺乏专业营销团队
- 营销自动化软件市场全球 2024 年超 65 亿美元
- 内容营销外包均价：完整活动策划 5 万-20 万元人民币
- AI 营销 SaaS 工具市场 CAGR > 40%（2023-2028）

### 竞品分析
| 产品 | 优势 | 劣势 |
|------|------|------|
| HubSpot | 全套营销自动化 | 价格极贵，复杂 |
| 蓝光数据 | 中文内容营销 | 偏向数据分析 |
| Jasper | AI 内容生成 | 无日历规划 |
| **本项目** | 一键生成完整日历 + 触达预估 + 本地运行 | 无真实发布集成 |

---

## 项目简介

一句话描述活动目标，自动生成完整的跨平台营销日历（最长 90 天），包含每日内容任务、阶段里程碑、触达量预估和 KPI 目标。支持 5 种活动类型和 6 个中国主流平台。

---

## 技术架构

```
活动名称 + 类型 + 周期 + 平台 + 预算
                │
                ▼
agent.py ─ run_plan_campaign()
                │
                ▼
tools/campaign_calendar.py
┌──────────────────────────────────────────────────┐
│  generate_campaign_calendar(                     │
│      campaign_name, type, start_date,            │
│      duration_days, platforms, budget            │
│  )                                               │
│                                                  │
│  _build_phase_tasks(phase, days, platforms)      │
│  _get_content_type_for_platform(platform)        │
│  format_campaign_markdown(plan)                  │
└────────────────────────┬─────────────────────────┘
                         │ CampaignPlan
                    ┌────┴──────┬──────────────────┐
                    │           │                  │
           run_get_platform_  run_get_phase_  run_estimate_
           schedule()         tasks()         reach()
                    │
              ┌─────┴─────┐
           app.py       api.py
         (Streamlit    (FastAPI
          :8501)        :8030)

活动阶段划分:
  预热 (15%)  → 话题铺垫，预告内容
  爆发 (30%)  → 集中投放，互动高峰
  持续 (40%)  → 长尾内容，口碑沉淀
  收尾 (15%)  → 复盘总结，转化承接
```

---

## 运行说明

```bash
cd project_30_openclaw_campaign_planner
uv pip install -r requirements.txt

# UI
uv run streamlit run app.py

# API
uv run uvicorn api:app --host 0.0.0.0 --port 8030 --reload
```

---

## 活动类型说明

| 类型 | 说明 | 典型场景 |
|------|------|---------|
| `product_launch` | 产品发布 | 新 App 上线、新品发布 |
| `brand_awareness` | 品牌曝光 | 品牌首进市场、年度宣传 |
| `seasonal` | 节日营销 | 618、双十一、春节 |
| `engagement` | 用户互动 | 话题挑战、UGC 征集 |
| `lead_generation` | 潜在客户 | B2B 获客、白皮书推广 |

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 + 支持的类型和平台 |
| GET | `/campaign/types` | 列出活动类型 |
| POST | `/campaign/plan` | 生成完整营销计划 |
| POST | `/campaign/plan/schedule` | 查询平台日程 |
| POST | `/campaign/reach` | 预估触达量 |
| GET | `/chat/stream` | SSE 流式对话 |

### 示例
```bash
# 生成 30 天品牌曝光活动
curl -X POST http://localhost:8030/campaign/plan \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_name": "国货之光2025",
    "campaign_type": "brand_awareness",
    "duration_days": 30,
    "platforms": ["微博", "小红书", "抖音"],
    "budget": 50000,
    "topic": "国货品牌，Z世代，国潮"
  }'

# 预估触达量
curl -X POST http://localhost:8030/campaign/reach \
  -H "Content-Type: application/json" \
  -d '{"campaign_name": "测试", "campaign_type": "seasonal"}'
```

---

## 触达量估算模型

```
平台基础触达量 × 内容数量 × 预算系数

微博：   5000 × n条 × 预算系数
小红书：  3000 × n条 × 预算系数
知乎：   2000 × n条 × 预算系数
抖音：   8000 × n条 × 预算系数
Twitter: 1000 × n条 × 预算系数
微信公众号: 4000 × n条 × 预算系数
```

---

## 评估结果

| 指标 | 数值 |
|------|------|
| 30 天活动规划生成 | < 300ms |
| 90 天活动规划生成 | < 500ms |
| 最大内容任务数 | 200（可配置） |
| 测试覆盖率 | 55 个测试，100% 通过 |

---

## OpenClaw 技能集成

- **content-publisher**: 多平台发布规则和时间策略
- **content-harvester**: 竞品内容监控，活动内容参考
- **rss-monitor**: 行业动态追踪，活动节点调整
- **OpenClaw Cron**: 按日历自动触发内容生产任务

---

## 后续改进方向

- [ ] 与 P27 热点追踪联动（热点触发活动规划）
- [ ] 与 P28 内容改写联动（活动内容自动生成）
- [ ] 与 P29 个人记忆联动（记住用户品牌风格偏好）
- [ ] 活动效果追踪（与实际数据对比计划）
- [ ] 预算智能分配算法（ROI 最大化）
- [ ] 导出 Excel 格式内容日历
- [ ] 竞品活动分析（爬取竞品营销动态）
