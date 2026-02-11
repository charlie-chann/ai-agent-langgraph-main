# config.py — openclaw 知乎内容 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.4   # 知乎偏严肃，温度低一些

PLATFORM = "zhihu"
MAX_ANSWER_LENGTH = 2000
MAX_ARTICLE_LENGTH = 5000
MAX_TAGS = 5
DAILY_POST_LIMIT = 3
OPTIMAL_POST_HOURS = [9, 14, 20]

PROHIBITED_WORDS_CHECK = True
SENSITIVE_TOPICS = ["医疗建议", "法律建议", "违法内容"]
