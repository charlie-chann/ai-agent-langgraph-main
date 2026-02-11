"""营销活动规划 Agent 配置"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.5

PLATFORM = "campaign_planner"

# 活动规划配置
MAX_CAMPAIGN_DAYS = 90         # 最大活动周期（天）
MIN_CAMPAIGN_DAYS = 3          # 最小活动周期
MAX_CONTENT_PIECES_PER_DAY = 5 # 每天最多内容条数
MAX_TOTAL_CONTENT = 200        # 整个活动最多内容数量

# 支持的活动类型
CAMPAIGN_TYPES = [
    "product_launch",    # 产品发布
    "brand_awareness",   # 品牌曝光
    "seasonal",          # 节日/季节营销
    "engagement",        # 用户互动
    "lead_generation"    # 潜在客户获取
]

# 支持的目标平台
TARGET_PLATFORMS = ["微博", "小红书", "知乎", "抖音", "Twitter", "微信公众号"]

# 内容类型及适配平台
CONTENT_TYPES = {
    "short_post": ["微博", "Twitter"],
    "image_text": ["微博", "小红书"],
    "long_article": ["知乎", "微信公众号"],
    "video_script": ["抖音"],
    "lifestyle_note": ["小红书"],
    "thread": ["Twitter"]
}

# 默认预算分配比例（各平台）
DEFAULT_BUDGET_ALLOCATION = {
    "微博": 0.25,
    "小红书": 0.30,
    "知乎": 0.15,
    "抖音": 0.20,
    "Twitter": 0.10
}

# 活动阶段
CAMPAIGN_PHASES = ["预热", "爆发", "持续", "收尾"]
