---
name: content-organizer
description: 内容整理与归档专家。将采集的碎片信息分类、标注、关联，形成可检索的知识库。
---

# Content Organizer

内容整理与归档技能。

## 使用场景

- 将采集的内容分类到知识库
- 给内容打标签、做标注
- 建立内容之间的关联
- 定期整理和淘汰过时内容

## 存储结构

```
C:\Users\charlie\my-docs\内容库\
├── 📥 收件箱\          # 刚采集的原始内容
├── 🏷️ 按主题\
│   ├── 科技\
│   ├── 财经\
│   ├── 国际\
│   └── [自定义话题]\
├── 📅 按时间\
│   ├── 2026-03\
│   └── 2026-02\
├── 🔥 热点追踪\        # 当前热点专题
└── 🗑️ 归档\           # 过时或低价值内容
```

## 文件命名规范

```
[日期]_[主题]_[来源简称]_[标题摘要].md
例：2026-03-19_伊朗局势_BBC_以伊战争最新进展.md
```

## Frontmatter 元数据

每个内容文件应包含：

```yaml
---
title: 文章标题
source: 来源
url: 原始链接
date: 2026-03-19
tags: [伊朗, 中东, 地缘政治]
status: raw|processed|published
summary: 一句话摘要
---
```

## 工作流

1. **采集** → 存入 📥 收件箱
2. **阅读** → 判断价值，决定处理方式
3. **归类** → 打标签，移至对应主题文件夹
4. **提炼** → 更新 summary 和要点
5. **发布** → 标记 status: published

## Obsidian 联动

推荐使用 Obsidian 管理内容库：
```bash
node C:/Users/charlie/.openclaw/workspace/skills/obsidian/SKILL.md
```

## 定期维护

- 每周清理 📥 收件箱
- 每月整理 🗑️ 归档区
- 热点话题用 MOC（Map of Content）集中管理
