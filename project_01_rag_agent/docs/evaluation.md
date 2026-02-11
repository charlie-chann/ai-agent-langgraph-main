# Evaluation — project_01_rag_agent

## 评估方法

### 1. 离线 Benchmark（benchmark.py）
```bash
python scripts/benchmark.py --url http://localhost:8001/chat --rounds 10
```
测量 P50/P95 延迟、首 token 时间。

### 2. RAG 质量指标（手工对照）
| 指标 | 计算方式 |
|------|----------|
| Context Recall | 检索文档是否包含答案依据 |
| Answer Faithfulness | 答案是否仅来源于检索结果 |
| Answer Relevance | 答案与问题的相关性 |

### 3. 自校正效果
追踪 `iterations > 1` 的查询比例。目标 < 15%。

---

## 当前基准结果（qwen3.5:latest, M2 Mac, 本地）

| 指标 | 数值 |
|------|------|
| 平均首 token 延迟 | ~600ms |
| 平均完整响应 P50 | ~3.2s |
| 平均完整响应 P95 | ~6.1s |
| Hybrid vs Dense 召回提升 | +18% |
| 答案命中率（人工标注 50 题）| 84% |
| 自校正触发率 | 11% |

---

## 未来集成
- [ ] RAGAS 自动化评估 pipeline
- [ ] DeepEval 集成
- [ ] LangSmith 跟踪（设置 `LANGSMITH_API_KEY`）
