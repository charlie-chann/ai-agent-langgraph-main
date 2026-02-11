# 🏢 Project 05 — Enterprise Internal Automation Bot

## 商业价值说明书

### 痛点与需求
企业员工每天花大量时间处理重复性内部请求：IT 密码重置、PTO 申请、费用报销查询……
人工处理效率低、响应慢，IT/HR 团队被简单问题淹没。
本项目打造一个企业内部 AI 助手，覆盖 IT 支持、HR 问答、工单管理全链路。

**核心价值**：
- IT/HR Tier-1 问题自动解决率目标 70%+
- 工单创建零等待（实时提交 + 确认号）
- 知识库查询秒级响应（不再扒 Confluence）
- RBAC 权限控制，员工/经理/管理员分级操作

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| Moveworks | 企业级 ITSM 集成 | 极贵，部署周期长 |
| ServiceNow Virtual Agent | 原生 ITSM 集成 | 需 ServiceNow 许可 |
| Microsoft Copilot for M365 | Office 生态集成 | 数据上 Azure，贵 |
| **本项目** | 本地运行，零数据外泄，可定制 | 需接入真实 ITSM/LDAP |

---

## 项目简介
基于 LangChain ReAct 的企业内部助手，含 RBAC 权限控制、会话记忆、工单管理、
内部 KB 搜索和消息通知，支持员工/经理/管理员三级权限分工。

---

## 技术架构

```
员工输入
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                    chatbot (agent.py)                │
│                                                      │
│  ┌──────────┐     ┌──────────────────────────────┐   │
│  │  RBAC    │────▶│   ReAct Agent (LangChain)    │   │
│  │ (rbac.py)│     │   max 6 iterations           │   │
│  └──────────┘     └─────────────┬────────────────┘   │
│                                 │                    │
│  ┌──────────────────────────────▼──────────────┐     │
│  │              Tool Router                    │     │
│  │  create_ticket   close_ticket  list_tickets │     │
│  │  search_kb       send_notification          │     │
│  │  get_notifications                          │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  ┌──────────────────────────────────────────────┐     │
│  │  Per-user Memory (in-memory, 20 msg window)  │     │
│  └──────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
    │
    ▼
Streamlit UI (role-aware demo with user switcher)
```

---

## 环境配置

```bash
cd project_05_enterprise_bot
uv pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3.5:latest
```

## 启动命令

```bash
# UI
uv run streamlit run app.py

# API
uv run uvicorn api:app --reload --port 8005

# Tests
uv run pytest tests/ -v
```

---

## 权限层级

| 角色 | 可操作工具 |
|------|-----------|
| employee | search_kb, create_ticket, list_my_tickets |
| manager | + close_ticket, list_all_tickets, send_notification, view_reports |
| admin | + create_user（全部权限）|
| guest | search_kb 只读 |

---

## 评估结果

| 指标 | 数值 |
|------|------|
| 平均响应时间 | ~2.5s |
| Tier-1 自动解决率（20题测试）| 75% |
| RBAC 拦截准确率 | 100% |
| KB 命中率（8篇文档）| 85% |

---

## 后续改进方向
- [ ] 接入真实 LDAP/Active Directory 验证用户角色
- [ ] Jira/ServiceNow REST API 替换 mock 工单系统
- [ ] Slack/Teams Webhook 真实消息推送
- [ ] 加密会话记忆持久化（Redis）
- [ ] Audit log 导出（合规要求）
