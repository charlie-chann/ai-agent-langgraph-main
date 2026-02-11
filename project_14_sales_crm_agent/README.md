# 💼 Project 14 — 销售 CRM Agent

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
中国 B2B SaaS 销售市场每年超 1000 亿，但销售团队效率极低。核心痛点：
- **销售漏斗管理粗放**：靠人工判断哪些线索值得跟进，准确率低
- **跟进邮件千篇一律**：通用模板效果差，个性化邮件撰写耗时
- **CRM 数据录入繁琐**：销售人员抗拒手工录入，数据质量差
- **转化率低**：B2B 平均销售周期 3-6 个月，错过时机点成本极高

本 Agent 通过多维度线索评分（预算/时间线/参与度/行业/联系人级别）自动识别高价值商机，配合个性化邮件生成，将销售跟进效率提升 5-10 倍。

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| Salesforce Einstein | 功能最全 | 年费极高，配置复杂 |
| 纷享销客/销售易 | 本土化好 | AI能力弱 |
| HubSpot | 免费入门 | 高级功能贵 |
| **本项目** | 本地运行，可定制评分模型，免费 | 需自己部署 |

---

## 项目简介

销售 CRM AI Agent，集成多维线索评分（hot/warm/cold）、个性化邮件生成（4种模板）、CRM CRUD 操作，所有输入经 XSS 防护处理。

## 技术架构

```
销售输入 (线索信息 / 邮件需求)
    ↓
lead_scorer.py    → 多维评分:
                     预算(30分) + 时间线(20分) + 参与度(25分)
                     + 行业(15分) + 联系人级别(10分) = 总分100
                     hot(≥70) / warm(40-69) / cold(<40)
    ↓
email_generator.py → 4种邮件模板:
                      first_contact / followup / proposal / nurture
                      _sanitize_field: XSS防护 (re.sub HTML标签)
crm_tool.py        → 状态机管理 (new→qualified→proposal→negotiation→won/lost)
                      邮箱格式验证
    ↓
agent.py           → 综合调度 + 日志
    ↓
app.py (Streamlit) ← UI
api.py (FastAPI)   ← REST API
```

## 功能特性

- ✅ 5 维度线索评分（总分 100）
- ✅ hot/warm/cold 分级 + 后续行动建议
- ✅ 4 种销售邮件模板（首次联系/跟进/提案/培育）
- ✅ XSS 防护（HTML 标签剥离）
- ✅ CRM 状态机（6阶段销售漏斗）
- ✅ 邮箱格式验证

## 运行说明

```bash
cd project_14_sales_crm_agent
uv run streamlit run app.py
uv run uvicorn api:app --port 8014 --reload
```

## 测试

```bash
uv run pytest tests/ -v
# 31/31 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 评分维度 | 5维（预算/时间/参与/行业/联系人） |
| XSS防护 | HTML标签100%剥离 |
| 邮件模板覆盖 | 4种销售场景 |
| 测试通过率 | 31/31 (100%) |

## 后续改进

- [ ] 接入 Salesforce / HubSpot API 双向同步
- [ ] ML 模型替代规则评分（基于历史成单数据）
- [ ] 添加线索来源追踪（UTM 参数）
- [ ] 邮件 A/B 测试框架
