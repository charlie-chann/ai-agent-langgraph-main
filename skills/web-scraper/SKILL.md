---
name: web-scraper
description: 网页数据抓取专家。能提取网页正文、表格、列表、特定元素。适用于：竞品监控、价格追踪、结构化数据采集。
---

# Web Scraper

网页数据抓取技能。

## 使用场景

- 抓取新闻文章正文
- 提取表格数据（价格、排名、统计）
- 批量采集列表页所有条目
- 抓取需要滚动加载的页面

## 工具

### 1. Tavily extract（推荐，最简单）
```bash
node C:/Users/charlie/.openclaw/workspace/skills/tavily-search/scripts/extract.mjs "URL"
```

### 2. Puppeteer（无头浏览器）
```bash
npm install puppeteer
node scripts/puppeteer-scrape.mjs "URL" "CSS_SELECTOR"
```

### 3. Cheerio（静态页面解析）
```bash
npm install cheerio
node scripts/cheerio-scrape.mjs "URL" "CSS_SELECTOR"
```

### 4. fetch + 正则（最轻量）
```bash
node scripts/fetch-regex.mjs "URL" "PATTERN"
```

## 常用 CSS 选择器

| 目标 | 选择器 |
|------|--------|
| 文章正文 | `article`, `.content`, `#article` |
| 标题 | `h1`, `.title`, `article h1` |
| 时间 | `time`, `.date`, `[datetime]` |
| 图片 | `img[src]`, `.post img` |
| 列表项 | `ul li`, `.item-list li` |
| 表格 | `table tr`, `.data-table tr` |

## 工作流

1. **分析页面结构** → 查看HTML找到目标元素
2. **选择工具** → 简单内容用Tavily，复杂结构用Puppeteer
3. **提取数据** → 运行抓取脚本
4. **清洗数据** → 去除广告/导航/无关内容
5. **结构化输出** → JSON或Markdown
6. **保存** → 存入 Obsidian 或数据库

## 示例：抓取新闻列表

```javascript
// scripts/news-list-scrape.mjs
import puppeteer from 'puppeteer';

const browser = await puppeteer.launch();
const page = await browser.newPage();
await page.goto('https://news.example.com');

const articles = await page.$$eval('article', els => 
  els.map(el => ({
    title: el.querySelector('h2')?.textContent,
    url: el.querySelector('a')?.href,
    date: el.querySelector('time')?.dateTime
  }))
);

await browser.close();
console.log(JSON.stringify(articles, null, 2));
```

## 注意事项

- robots.txt 规则要遵守
- 爬取频率不要过高（≥2秒间隔）
- 登录后才能访问的页面需要 Cookie/Session
- 动态渲染页面必须用 Puppeteer
- 优先抓取 RSS/API 等结构化数据源
