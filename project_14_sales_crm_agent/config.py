# config.py — 销售 CRM Agent 配置
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.3   # 邮件生成用稍高温度

# Lead 评分阈值
LEAD_HOT_SCORE = 70      # ≥70 → 热线索
LEAD_WARM_SCORE = 40     # 40-69 → 温线索
LEAD_COLD_SCORE = 0      # <40 → 冷线索

# 跟进策略
MAX_FOLLOWUP_DAYS = 7    # 超过7天未联系需重新跟进
EMAIL_MAX_LENGTH = 500   # 邮件正文最大字符数
