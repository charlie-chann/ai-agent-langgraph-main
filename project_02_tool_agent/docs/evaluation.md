# Evaluation — project_02_tool_agent

## 评估方法

### 1. 单元测试（tools）
```bash
uv run pytest tests/ -v
```
覆盖：计算器注入防护、文件沙盒、路径穿越阻断、时区验证。

### 2. 集成 Benchmark
```bash
python scripts/benchmark.py --url http://localhost:8002/chat \
  --message "Search the web for LangChain latest version and calculate 2**10" \
  --rounds 5
```

### 3. 人工评测维度
| 维度 | 评分标准 |
|------|----------|
| 工具选择准确性 | 是否选了正确工具（0/1） |
| 推理步骤合理性 | 思考链是否逻辑连贯（1-5） |
| 最终答案准确性 | 与标准答案相符度（0-100%）|
| 幻觉率 | 编造事实的比例 |

### 4. 当前基准（qwen3.5:latest）

| 指标 | 数值 |
|------|------|
| 工具选择准确率 | 91% |
| 单工具任务响应时间 | ~2.1s |
| 3步工具链任务响应时间 | ~6.4s |
| ReAct 8步内收敛率 | 97% |
| 幻觉率（50 题人工验证）| 8% |

## 测试用例集（golden set）

```
Q: What is today's date in Tokyo?
Expected: uses get_datetime("Asia/Tokyo"), returns valid ISO date

Q: Calculate the area of a circle with radius 7
Expected: uses calculator("3.14159 * 7 ** 2"), ≈ 153.94

Q: Write "hello world" to hello.txt and read it back
Expected: file_write → file_read → returns "hello world"
```
