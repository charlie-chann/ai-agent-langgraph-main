---
name: rss-monitor
description: RSS订阅监控专家。追踪多个信息源，自动发现更新，触发采集流程。
---

# RSS Monitor

RSS 订阅监控技能。

## 使用场景

- 监控多个新闻源/博客的更新
- 设定关键词过滤，只采集感兴趣的内容
- 定时检查新内容并推送提醒
- 构建信息获取管道

## 工具

### 1. blogwatcher（推荐，已集成）
```bash
node C:/Users/charlie/AppData/Roaming/npm/node_modules/openclaw/skills/blogwatcher/SKILL.md
```

### 2. rss-parser（Node.js）
```bash
npm install rss-parser
node scripts/rss-parse.mjs "RSS_URL"
```

### 3. 在线RSS服务
- https://fetchrss.com（无需API）
- https://rss.app

## 推荐的订阅源

```
# 新闻
https://rss.cctv.com/rss/news.rss          # CCTV新闻
https://feeds.bbci.co.uk/news/world/rss.xml  # BBC国际
https://www.zaobao.com.sg/rss/realtime/china  # 联合早报

# 科技
https://feeds.feedburner.com/Slashdot    # Slashdot
https://hnrss.org/frontpage              # Hacker News

# 行业
[根据你的行业添加]
```

## 工作流

1. **配置源列表** → 保存到 `C:\Users\charlie\work\ai_agent_dev\data\rss-sources.json`
2. **设定频率** → 通过 cron 定时执行（建议每2小时一次）
3. **关键词过滤** → 只采集包含特定词的内容
4. **自动采集** → 发现新内容后调用 content-harvester
5. **推送通知** → 有重大更新时通知用户

## 配置文件格式

```json
{
  "sources": [
    {
      "name": "BBC World",
      "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
      "tags": ["国际", "新闻"],
      "keywords": ["伊朗", "以色列", "中东"],
      "enabled": true
    }
  ],
  "checkInterval": "2h",
  "notificationThreshold": "high"
}
```

## 注意事项

- 不要过于频繁检查（尊重源服务器）
- 图片优先保存到本地再引用
- 视频内容记录标题和时间，后续单独处理
