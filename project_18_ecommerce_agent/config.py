# config.py — 电商自动化 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.4   # 商品描述用较高创意度

# 竞品监控
PRICE_ALERT_PCT = 10        # 对手价格变动超10% → 预警
MAX_COMPETITORS = 20        # 最多监控竞品数量

# 商品描述生成
DESC_MAX_LENGTH = 300        # 商品描述最大字符数
SEO_KEYWORDS_COUNT = 5       # 最多提取5个 SEO 关键词
