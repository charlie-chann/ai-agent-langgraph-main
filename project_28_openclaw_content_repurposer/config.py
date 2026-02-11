"""内容二次加工 Agent 配置"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.7  # 内容创作需要适度创意

PLATFORM = "content_repurposer"

# 各平台内容规格
PLATFORM_SPECS = {
    "weibo": {
        "max_chars": 2000,
        "tone": "casual",
        "format": "短文+hashtag",
        "hashtag_count": 3,
        "emoji_allowed": True
    },
    "xiaohongshu": {
        "max_chars": 1000,
        "tone": "lifestyle",
        "format": "标题+正文+标签",
        "hashtag_count": 5,
        "emoji_allowed": True
    },
    "zhihu": {
        "max_chars": 5000,
        "tone": "professional",
        "format": "问答/文章",
        "hashtag_count": 0,
        "emoji_allowed": False
    },
    "douyin": {
        "max_chars": 500,
        "tone": "entertaining",
        "format": "视频脚本/文案",
        "hashtag_count": 5,
        "emoji_allowed": True
    },
    "twitter": {
        "max_chars": 280,
        "tone": "concise",
        "format": "tweet/thread",
        "hashtag_count": 2,
        "emoji_allowed": True,
        "language": "en"
    }
}

DEFAULT_TARGET_PLATFORMS = list(PLATFORM_SPECS.keys())

# 内容适配风格
ADAPTATION_STYLES = {
    "casual": "轻松、生活化、亲切",
    "professional": "专业、深度、有见地",
    "entertaining": "有趣、生动、吸引注意力",
    "lifestyle": "种草、感受、生活方式"
}
