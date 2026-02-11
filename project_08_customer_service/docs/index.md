# docs/index.md — 项目08：客服全链路 Agent

## 文档索引

| 文档 | 说明 |
|------|------|
| [架构设计](architecture.md) | 系统架构、Agent流程、工具调用 |
| [API参考](api_reference.md) | REST + SSE 接口文档 |
| [评估报告](evaluation.md) | 测试结果与基准指标 |
| [变更日志](changelog.md) | 版本历史 |

---

## 项目概述

**客服全链路 Agent** 是一套 AI 驱动的端到端客户服务系统，能够自动识别用户意图、搜索知识库答疑、查询订单物流、创建和管理工单，并根据用户情感状态智能决策是否升级到人工客服。

### 核心能力
- **意图识别** — 自动分类：退款/投诉/订单查询/技术支持/账号问题/账单
- **知识库问答** — BM25 全文检索 12 篇 FAQ，可随时扩充
- **情感感知** — 关键词权重评分，负面分 ≥0.7 自动升级
- **工单全流程** — 创建、查询、更新、升级；P1-P4 优先级 + SLA 追踪
- **订单查询** — 模拟真实物流轨迹，支持多状态
- **多轮对话** — 用户级别的会话记忆（最近10轮）

### 快速启动
```bash
cd project_08_customer_service
cp .env.example .env
uv run streamlit run app.py
```

### 运行测试
```bash
uv run pytest tests/ -v
```
