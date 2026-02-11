# config.py — 运维故障根因分析 Agent
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.1

# 日志分析参数
MAX_LOG_LINES = 1000         # 单次分析最大日志行数
ERROR_KEYWORDS = ["ERROR", "FATAL", "CRITICAL", "Exception", "Traceback", "OOM", "timeout"]
WARNING_KEYWORDS = ["WARN", "WARNING", "deprecated", "retry"]

# 工单参数
TICKET_PREFIX = "OPS"
AUTO_ASSIGN_CRITICAL = True  # 严重故障自动分配
