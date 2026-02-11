"""热点追踪 Agent 配置"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.3

PLATFORM = "trend_tracker"

# 趋势检测配置
TREND_WINDOW_HOURS = 24         # 趋势检测时间窗口（小时）
MIN_MENTIONS_FOR_TREND = 3      # 至少出现次数才算趋势
MAX_TRACKED_TOPICS = 20         # 最多追踪话题数
HEAT_SCORE_DECAY = 0.85         # 热度衰减系数（每小时）
ALERT_THRESHOLD = 0.8           # 触发预警的热度阈值

# 热度级别
HEAT_LEVELS = {
    "cold": (0.0, 0.3),
    "warming": (0.3, 0.6),
    "hot": (0.6, 0.8),
    "trending": (0.8, 1.0)
}

# 内容机会分析
CONTENT_OPPORTUNITY_PLATFORMS = ["微博", "小红书", "知乎", "抖音", "Twitter"]

# 数据来源权重
SOURCE_WEIGHT = {
    "weibo": 0.8,
    "wechat": 0.9,
    "news": 1.0,
    "douyin": 0.7,
    "twitter": 0.75
}
