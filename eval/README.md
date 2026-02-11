# Agent Eval 体系（7 步最小可用版）

面向 `project_01_rag_agent` 与 **`project_00_rag_agent`**，实现：**评测集 → Prompt 版本化 → 批量跑 → 规则/Judge 打分 → trace 归因 → 回归门禁 → 单变量迭代**。

## 目录

```
eval/
├── datasets/rag_qa.jsonl      # 步骤1：评测集
├── prompts/
│   ├── rag_v1.txt             # 步骤2：Prompt 版本
│   ├── rag_v2.txt
│   └── judge_faithfulness.txt # 步骤4：LLM Judge
├── baseline.json              # 步骤6：回归基线
├── results/                   # 每次 eval 输出
└── harness/
    ├── run_eval.py            # 步骤3/4/5/6 主入口
    ├── compare.py             # 步骤7：A/B 对比
    ├── prompt_loader.py       # 步骤2
    ├── metrics.py             # 步骤4a 规则分
    ├── judge.py               # 步骤4b LLM Judge
    ├── trace_analysis.py      # 步骤5
    └── regression.py          # 步骤6
```

## 快速开始

```bash
# 1. 确保 project_00 已 ingest 且 Ollama 在跑
cd project_00_rag_agent
python -c "from tools.ingest import ingest_files; print(ingest_files(['sample_docs/company_knowledge_base.txt']))"

# 2. 跑 eval（默认 project_00）
python eval/harness/run_eval.py --project 00 --prompt v1

# 3. 对比 project_01（legacy）
python eval/harness/run_eval.py --project 01 --prompt v1

# 3. 写入基线
python eval/harness/run_eval.py --prompt v1 --update-baseline

# 4. 单变量迭代：只改 rag_v2.txt，再跑
python eval/harness/run_eval.py --prompt v2 --regression

# 5. 对比两次结果
python eval/harness/compare.py \
  --a eval/results/rag_v1_YYYYMMDD_HHMMSS.json \
  --b eval/results/rag_v2_YYYYMMDD_HHMMSS.json
```

无 Ollama 时可先：`python eval/harness/run_eval.py --prompt v1 --no-judge`
