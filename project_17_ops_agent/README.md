# 🖥️ Project 17 — 智能运维 Agent

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
中国互联网企业 IT 基础设施规模庞大，系统故障的平均代价是每分钟 5-10 万元（MTTR 越长损失越大）。核心痛点：
- **日志量爆炸**：大型系统每天产生 TB 级日志，人工排查如大海捞针
- **故障定位慢**：平均故障定位（MTTD）需要 30-60 分钟
- **根因分析难**：分布式系统中，表面问题（HTTP 500）和根因（DB 连接池耗尽）之间关系复杂
- **告警疲劳**：大量误报导致运维工程师对告警麻木

本 Agent 实现日志自动解析 → 根因定位 → RCA 报告生成 → 工单创建全流程自动化，将 MTTD 从 30 分钟压缩到 30 秒。

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| Datadog | 监控全面 | 极贵（$10-50/主机/月） |
| 阿里云 ARMS | 国内部署好 | 依赖阿里生态 |
| ELK Stack | 开源免费 | 需要大量配置 |
| **本项目** | 本地运行，AI根因分析，免费 | 需接入日志采集 |

---

## 项目简介

智能运维 AI Agent，集成日志解析、多优先级根因检测（数据库/OOM/磁盘/网络/应用）、RCA 报告生成和工单创建。

## 技术架构

```
日志输入 (原始日志文本)
    ↓
log_analyzer.py → 日志结构化解析 (timestamp/level/service/message)
    ↓
                → 根因检测 (优先级顺序):
                   1. DB连接超时 (db_timeout 关键词)
                   2. 内存溢出 OOM (java.lang.OutOfMemoryError)
                   3. 磁盘空间不足 (disk/space)
                   4. 网络连接失败 (connection refused)
                   5. 应用错误 (exception/error)
    ↓
                → RCA报告生成 (markdown格式)
                → 工单创建 (UUID工单号)
    ↓
agent.py        → 综合调度
    ↓
app.py (Streamlit) ← UI
api.py (FastAPI)   ← REST API
```

## 功能特性

- ✅ 日志结构化解析（timestamp/level/service/message）
- ✅ 5级根因检测（DB > OOM > 磁盘 > 网络 > 应用）
- ✅ 自动 RCA 报告（markdown 格式，含时间线）
- ✅ 工单自动创建（UUID 工单号）
- ✅ 故障级别评估（critical/high/medium/low）

## 运行说明

```bash
cd project_17_ops_agent
uv run streamlit run app.py
uv run uvicorn api:app --port 8017 --reload
```

## 测试

```bash
uv run pytest tests/ -v
# 13/13 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 根因检测分类 | 5类（按优先级顺序） |
| 日志解析格式 | 正则通用格式 |
| 工单号格式 | UUID 前8位 |
| 测试通过率 | 13/13 (100%) |

## 后续改进

- [ ] 接入 Prometheus/Grafana 实时指标
- [ ] ML 异常检测（孤立森林/LSTM）
- [ ] 自动执行修复脚本（自愈能力）
- [ ] 多集群关联分析（Kubernetes）
