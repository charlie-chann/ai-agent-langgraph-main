# AI Agent 项目清单 (plan001)

> 本文件只记录项目列表和状态，不含背景分析。  
> 技术规范详见 `.github/copilot-instructions.md`。

---

## 一、已完成项目（projects 01~14）

| 编号 | 文件夹 | 项目名 | 优先级 | 状态 |
|------|--------|--------|--------|------|
| 01 | `project_01_rag_agent` | 企业级 RAG + Agentic RAG | P0 | ✅ 完成 |
| 02 | `project_02_tool_agent` | 多工具调用 ReAct Agent | P0 | ✅ 完成 |
| 03 | `project_03_multi_agent` | 多智能体协作系统 | P0 | ✅ 完成 |
| 04 | `project_04_deep_research` | 深度研究 Agent | P0 | ✅ 完成 |
| 05 | `project_05_enterprise_bot` | 企业内部自动化助手 | P1 | ✅ 完成 |
| 06 | `project_06_code_agent` | 代码/DevOps Agent | P1 | ✅ 完成 |
| 07 | `project_07_finance_agent` | 金融/合规分析 Agent | P1 | ✅ 完成 |
| 08 | `project_08_customer_service` | 客服全链路 Agent | P1 | ✅ 完成 |
| 09 | `project_09_browser_agent` | 浏览器自动化 Agent | P2 | ✅ 完成 |
| 10 | `project_10_hr_agent` | HR/招聘筛选 Agent | P2 | ✅ 完成 |
| 11 | `project_11_legal_agent` | 法律合同审查 Agent | P2 | ✅ 完成 |
| 12 | `project_12_quant_agent` | 量化研究 Agent | P2 | ✅ 完成 |
| 13 | `project_13_medical_agent` | 医疗辅助 Agent | P2 | ✅ 完成 |
| 14 | `project_14_sales_crm_agent` | 销售/CRM Agent | P2 | ✅ 完成 |

---

## 二、待开发项目（projects 15~24）

> 本批次引入 **openclaw** 系列（自动化内容生成 + 社交媒体管理），  
> 以及企业级高价值赛道，共 10 个项目。

| 编号 | 文件夹 | 项目名 | 优先级 | 核心价值 |
|------|--------|--------|--------|----------|
| 15 | `project_15_supply_chain_agent` | 供应链/物流优化 Agent | P3 | 库存预测、路径优化、异常预警 |
| 16 | `project_16_education_agent` | 个性化教育 Agent | P3 | 学习规划、题目讲解、自适应出题 |
| 17 | `project_17_ops_agent` | 运维故障根因分析 Agent | P3 | 日志分析、自动工单、RCA 报告 |
| 18 | `project_18_ecommerce_agent` | 电商自动化 Agent | P3 | 竞品监控、调价建议、商品描述生成 |
| 19 | `project_19_privacy_agent` | 本地隐私 Agent | P3 | 全离线运行、PII 保护、政企合规 |
| 20 | `project_20_openclaw_weibo` | openclaw 微博内容 Agent | P3 | 自动生成微博 + 评论互动 + 定时发布 |
| 21 | `project_21_openclaw_xiaohongshu` | openclaw 小红书 Agent | P3 | 图文笔记生成 + SEO 标签优化 + 发布 |
| 22 | `project_22_openclaw_zhihu` | openclaw 知乎 Agent | P3 | 问答回复生成 + 专栏文章 + 引流 |
| 23 | `project_23_openclaw_douyin` | openclaw 抖音脚本 Agent | P3 | 视频脚本生成 + 字幕 + 话题标签 |
| 24 | `project_24_openclaw_twitter` | openclaw Twitter/X Agent | P3 | 英文推文生成 + Thread + 定时发布 |

---

## 三、openclaw 系列说明

openclaw 是一组社交媒体自动化工具，定位为：

- **内容生产**：通过 LLM 自动生成适合各平台调性的内容（中英文）
- **管理调度**：统一管理多平台发布时间、账号、内容队列
- **数据回流**：抓取互动数据（点赞/评论/转发）→ 反馈给 Agent 优化下一轮内容
- **合规设计**：内容审查（广告法、违禁词过滤）、频率限制、账号轮换

每个 openclaw 子项目遵循：

```
project_2X_openclaw_XXX/
├── agent.py              # 内容生成 Agent
├── publisher.py          # 发布调度器（模拟/真实）
├── scraper.py            # 互动数据采集（可 mock）
├── tools/
│   ├── content_generator.py   # 平台调性内容生成
│   ├── tag_optimizer.py       # 话题/标签优化
│   └── schedule_tool.py       # 发布时间规划
├── tests/
└── ...
```

---

## 四、项目总进度

```
已完成: 14/24  (58%)
待开发: 10/24  (42%)

P0 完成: 4/4  ✅
P1 完成: 4/4  ✅
P2 完成: 6/6  ✅
P3 待开发: 0/10
```
