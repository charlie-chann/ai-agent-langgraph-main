# config.py — 供应链/物流优化 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.1

# 库存预警阈值（天）
STOCK_LOW_DAYS = 7       # 库存低于7天用量 → 预警
STOCK_CRITICAL_DAYS = 3  # 库存低于3天用量 → 紧急补货

# 路径优化
MAX_ROUTE_STOPS = 20     # 单次配送最多20个站点
SPEED_KMH = 60           # 平均行驶速度（km/h）

# 异常检测
DELAY_THRESHOLD_HOURS = 2   # 超过2小时延误 → 触发预警
COST_SPIKE_PCT = 30         # 成本涨幅超30% → 异常
