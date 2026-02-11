# 🖤 私人助手技能库

> 内容获取 → 整理 → 发布 全流程技能体系

## 📚 技能一览

| 技能 | 名称 | 职责 |
|------|------|------|
| `content-harvester/` | 内容采集 | 多源内容抓取（Tavily/RSS/网页） |
| `content-summarizer/` | 内容摘要 | 长文压缩、视频摘要、多风格改写 |
| `content-organizer/` | 内容整理 | 分类归档、标签管理、知识库维护 |
| `rss-monitor/` | 订阅监控 | RSS追踪、自动发现更新、推送提醒 |
| `content-publisher/` | 内容发布 | Twitter/飞书/博客/公众号多平台发布 |
| `web-scraper/` | 网页抓取 | 结构化数据、列表、表格精准提取 |
| `deep-research/` | 深度调研 | 系统性专题研究、交叉验证、报告 |
| `content-aggregator/` | 内容聚合 | 早报/周报/专题报告生成 |

## 🔄 完整工作流

```
[ rss-monitor ] 定时监控订阅源
       ↓
[ content-harvester ] 采集新内容
       ↓
[ content-organizer ] 分类归档到 Obsidian
       ↓
[ content-summarizer ] 提炼摘要
       ↓
[ content-aggregator ] 生成早报/周报
       ↓
[ content-publisher ] 发布到各平台
```

## 📁 目录结构

```
ai_agent_dev/
├── skills/
│   ├── content-harvester/
│   ├── content-summarizer/
│   ├── content-organizer/
│   ├── rss-monitor/
│   ├── content-publisher/
│   ├── web-scraper/
│   ├── deep-research/
│   └── content-aggregator/
├── data/
│   ├── rss-sources.json      # RSS订阅源配置
│   ├── topics.json           # 关注话题配置
│   └── platforms.json        # 发布平台配置
└── scripts/                  # 公共脚本
    ├── rss-fetch.mjs
    ├── batch-harvest.mjs
    └── report-template.mjs
```

## 🚀 快速开始

**采集某个话题：**
```bash
node skills/content-harvester/scripts/search.mjs "伊朗最新动态" --topic news --days 7
```

**生成今日简报：**
```bash
node skills/content-aggregator/scripts/daily-briefing.mjs
```

**监控RSS更新：**
```bash
node skills/rss-monitor/scripts/check-all.mjs
```

## ⚡ 按需调用原则

- 信息采集 → `content-harvester`
- 想快速了解→ `content-summarizer`
- 整理归类 → `content-organizer`
- 定时监控 → `rss-monitor`
- 多篇整合 → `content-aggregator`
- 深度研究 → `deep-research`
- 精准抓取 → `web-scraper`
- 对外发布 → `content-publisher`

---

_原力与我同在 🖤_
