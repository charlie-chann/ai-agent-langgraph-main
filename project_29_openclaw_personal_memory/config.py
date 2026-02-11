"""个人记忆 Agent 配置 - OpenClaw 核心能力：持久化记忆"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.3

PLATFORM = "personal_memory"

# 记忆配置
MAX_MEMORY_ENTRIES = 1000        # 最大记忆条目数
MAX_CONTENT_LENGTH = 2000        # 单条记忆最大字符数
MAX_SEARCH_RESULTS = 10          # 搜索返回最多结果数
MEMORY_SIMILARITY_THRESHOLD = 0.6  # 相似度搜索阈值

# 记忆类型
MEMORY_TYPES = [
    "fact",         # 事实/知识
    "preference",   # 偏好/习惯
    "task",         # 待办/任务
    "event",        # 事件/日历
    "person",       # 人物/联系人
    "note",         # 笔记/备忘
    "insight"       # 洞察/思考
]

# 重要性级别
IMPORTANCE_LEVELS = ["low", "medium", "high", "critical"]

# 存储路径
MEMORY_STORE_PATH = "memory_store"

# 自动标签（召回时增强关联）
AUTO_TAG_KEYWORDS = {
    "工作": ["工作", "项目", "会议", "报告", "同事"],
    "学习": ["学习", "课程", "笔记", "书籍", "知识"],
    "健康": ["健康", "运动", "饮食", "睡眠", "医院"],
    "财务": ["钱", "财务", "投资", "预算", "消费"],
}
