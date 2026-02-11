# 📈 Project 12 — 量化金融分析 Agent

## 商业价值说明书

### 为什么这个 Agent 有市场需求？
中国 A 股散户占比 80%，年亏损率超 70%，核心原因是缺乏专业的技术分析工具和风险管理框架。痛点：
- **技术指标计算复杂**：RSI、MACD、布林带、ATR 需要专业金融知识
- **基本面分析耗时**：DCF 估值、格雷厄姆数等模型需要数小时手工计算
- **风险量化缺失**：VaR、夏普比率、最大回撤等专业指标普通投资者不会用
- **量化工具贵**：Bloomberg 终端年费 24000 美元，Wind 年费 20 万元人民币

本 Agent 将专业量化分析能力免费开放，让普通投资者也能进行专业级风险评估。

### 市场竞品分析
| 竞品 | 优势 | 劣势 |
|------|------|------|
| Bloomberg | 数据最全 | 极贵（24000美元/年） |
| 同花顺/东方财富 | 中国市场优化 | 数据滞后，功能有限 |
| QuantConnect | 回测强 | 需要编程，学习曲线陡 |
| **本项目** | 本地运行，免费，可扩展 | 需自行接入实时数据 |

---

## 项目简介

量化金融 AI 分析 Agent，集成技术指标计算（SMA/EMA/RSI/MACD/布林带/ATR）、基本面估值（DCF/格雷厄姆/PE）、组合风险评估（夏普/VaR/最大回撤/Beta）。

## 技术架构

```
输入: 股票代码 + 价格序列/财务数据
    ↓
technical_indicators.py → SMA/EMA/RSI/MACD/Bollinger/ATR
fundamental_metrics.py  → P/E ratio, Graham Number, DCF估值, ROE, EPS增长
portfolio_risk.py        → 夏普比率, 最大回撤, VaR(95%), Beta, 年化收益
    ↓
agent.py → 综合分析报告 + ticker合规验证 ([A-Z0-9.^-]{1,10})
    ↓
app.py (Streamlit) ← UI
api.py (FastAPI)   ← REST API
```

## 功能特性

- ✅ 6 种技术指标（SMA/EMA/RSI/MACD/布林带/ATR）
- ✅ 5 种基本面指标（PE/格雷厄姆/DCF/ROE/EPS增长）
- ✅ 5 种风险指标（夏普/最大回撤/VaR/Beta/波动率）
- ✅ 股票代码安全验证（防注入）
- ✅ 综合分析报告生成

## 运行说明

```bash
cd project_12_quant_agent
uv run streamlit run app.py
uv run uvicorn api:app --port 8012 --reload
```

## 测试

```bash
uv run pytest tests/ -v
# 29/29 ✅
```

## 评估结果

| 指标 | 数值 |
|------|------|
| 技术指标计算精度 | 与 pandas-ta 一致 |
| 夏普比率边界处理 | 零波动率 → Sharpe = 0.0 |
| VaR置信度 | 95% (正态分布假设) |
| 测试通过率 | 29/29 (100%) |

## 后续改进

- [ ] 接入 Yahoo Finance / AKShare 实时数据
- [ ] 添加回测框架（Backtrader 集成）
- [ ] 支持期权定价（Black-Scholes）
- [ ] 多因子模型（Fama-French 3因子）

> **风险提示**：本工具仅供学习研究，不构成投资建议。
