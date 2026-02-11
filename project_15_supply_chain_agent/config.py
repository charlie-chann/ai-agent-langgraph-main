# config.py — 供应链/物流优化 Agent 全局配置
#
# 【职责】管理 LLM 连接、库存预警阈值、路径优化参数。
# 算法工具（inventory_tool / route_optimizer）直接读取这些常量。

# ── Ollama LLM（仅 stream_chat 对话使用）────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.1

# ── 库存预警阈值（单位：天）──────────────────────────────────────────────────
STOCK_LOW_DAYS = 7       # 库存可支撑天数 < 7 → 预警（low）
STOCK_CRITICAL_DAYS = 3  # 库存可支撑天数 < 3 → 紧急补货（critical）

# ── 路径优化参数 ─────────────────────────────────────────────────────────────
MAX_ROUTE_STOPS = 20     # 单次配送最多站点数（TSP 规模限制）
SPEED_KMH = 60           # 平均行驶速度，用于估算配送耗时

# ── 异常检测阈值 ─────────────────────────────────────────────────────────────
DELAY_THRESHOLD_HOURS = 2   # 超过 2 小时延误 → 触发预警
COST_SPIKE_PCT = 30         # 成本涨幅超 30% → 标记异常
