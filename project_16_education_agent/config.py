# config.py — 个性化教育 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.3

# 学习规划参数
DEFAULT_STUDY_DAYS = 30      # 默认学习周期（天）
MIN_DAILY_MINUTES = 30       # 最少每日学习分钟
MAX_DAILY_MINUTES = 240      # 最多每日学习分钟

# 出题参数
QUESTION_DIFFICULTY_LEVELS = ["easy", "medium", "hard"]
PASS_SCORE_PCT = 70          # 及格分数线（%）
