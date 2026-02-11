---
name: content-harvester
description: 多源内容采集专家。能从网页、RSS、Tavily搜索、Twitter抓取内容。适用于：信息收集、竞品监控、行业动态追踪。
---

# Content Harvester

内容采集技能，支持多种来源。

## 使用场景

- 采集指定话题的最新内容
- 监控多个信息源
- 批量获取文章/帖子

## 工具

### 1. Tavily 搜索（推荐）
```bash
node C:/Users/charlie/.openclaw/workspace/skills/tavily-search/scripts/search.mjs "关键词" --topic news --days 7
```

### 2. 深度抓取页面内容
```bash
node C:/Users/charlie/.openclaw/workspace/skills/tavily-search/scripts/extract.mjs "URL"
```

### 3. RSS 订阅源采集
使用 rss-parser 或直接 fetch:
```bash
node scripts/rss-fetch.mjs "RSS_URL"
```

### 4. Twitter 抓取
使用 twitter-post skill 的反向能力抓取用户推文。

## 工作流

1. 明确采集目标（主题、来源、数量）
2. 选择合适的采集方式
3. 提取内容片段（不超过5条关键摘要）
4. 记录原始链接和来源时间
5. 输出结构化结果

## 输出格式

```
## 📥 采集结果：[主题]

### 来源 1
- **标题**：[标题]
- **摘要**：[核心内容，100字内]
- **链接**：[URL]
- **时间**：[YYYY-MM-DD]

...
```

## 注意事项

- 优先使用 Tavily（已集成），速度快且对AI友好
- 网页直接抓取用 extract.mjs
- 采集内容默认存储到 Obsidian：`C:\Users\charlie\my-docs\内容库\`
