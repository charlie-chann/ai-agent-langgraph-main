# config.py — openclaw 抖音脚本 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.8   # 抖音要吸睛，高创意度

PLATFORM = "douyin"
MAX_SCRIPT_LENGTH = 1000     # 脚本字数
MAX_TITLE_LENGTH = 35        # 视频标题
MAX_TAGS = 8
DAILY_POST_LIMIT = 3
OPTIMAL_POST_HOURS = [12, 18, 21, 22]
VIDEO_DURATIONS = [15, 30, 60, 180]  # 支持的视频时长（秒）

PROHIBITED_WORDS_CHECK = True
SENSITIVE_TOPICS = ["违法内容", "诈骗", "低俗"]
