# config.py — openclaw 微博内容 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.7   # 内容生成用较高创意度

# 平台规格
PLATFORM = "weibo"
MAX_CONTENT_LENGTH = 140          # 微博单条最长字符数
MAX_TAGS = 5                      # 最多话题标签数
DAILY_POST_LIMIT = 10             # 每日最多发帖数
OPTIMAL_POST_HOURS = [8, 12, 18, 21]  # 最佳发布时间

# 内容审查
PROHIBITED_WORDS_CHECK = True
SENSITIVE_TOPICS = ["政治", "宗教冲突", "违法内容"]
