# config.py — openclaw 小红书内容 Agent 全局配置
#
# 【职责】管理 LLM 连接、小红书平台规则（字数/标签/发帖限制）、合规检查开关。

# ── Ollama LLM（stream_chat 对话 + 内容工具模板生成）────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.7  # 内容创作温度略高，输出更有创意

# ── 小红书平台规则 ─────────────────────────────────────────────────────────────
PLATFORM = "xiaohongshu"       # 平台标识，传给 schedule/tag 工具
MAX_TITLE_LENGTH = 30          # 标题最大字数（小红书限制）
MAX_CONTENT_LENGTH = 1000      # 正文最大字数
MAX_TAGS = 10                  # 单篇笔记最多标签数
DAILY_POST_LIMIT = 5           # 每日建议发布上限
OPTIMAL_POST_HOURS = [10, 15, 20, 22]  # 最佳发布小时（plan_schedule 使用）

# ── 合规检查 ─────────────────────────────────────────────────────────────────
PROHIBITED_WORDS_CHECK = True  # 是否检查违禁词
SENSITIVE_TOPICS = ["违法内容", "诈骗", "虚假广告"]  # 敏感话题黑名单
