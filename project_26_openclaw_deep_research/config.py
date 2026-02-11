"""深度调研 Agent 配置"""

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.2  # 低温以保证分析严谨性

PLATFORM = "deep_research"

# 调研配置
MAX_SOURCES_PER_QUERY = 8       # 每个查询最多抓取来源数
MAX_QUERIES_PER_TOPIC = 5       # 每个话题最多生成查询数
MAX_REPORT_LENGTH = 8000        # 报告最大字符数
MIN_SOURCE_CREDIBILITY = 0.6    # 最低可信度阈值
CROSS_VALIDATE_THRESHOLD = 2    # 跨来源验证所需最少来源数

# 调研深度级别
RESEARCH_DEPTHS = ["quick", "standard", "deep"]
DEFAULT_DEPTH = "standard"

# 报告结构
REPORT_SECTIONS = [
    "executive_summary",    # 执行摘要
    "key_findings",         # 主要发现
    "data_analysis",        # 数据分析
    "source_validation",    # 来源验证
    "contradictions",       # 矛盾点
    "conclusions",          # 结论
    "further_reading"       # 延伸阅读
]

# 可信度权重（不同来源类型）
SOURCE_CREDIBILITY_WEIGHTS = {
    "academic": 0.95,
    "news": 0.75,
    "blog": 0.55,
    "social": 0.40,
    "unknown": 0.50
}

REPORTS_DIR = "reports"
