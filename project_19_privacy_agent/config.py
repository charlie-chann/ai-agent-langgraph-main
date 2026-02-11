# config.py — 本地隐私 Agent（全离线运行）
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.1

# 隐私保护配置
PII_DETECTION_ENABLED = True
AUDIT_LOG_PATH = "logs/audit.log"
DATA_RETENTION_DAYS = 30     # 本地数据保留天数

# 合规级别
COMPLIANCE_MODE = "strict"   # "strict" | "standard"
ALLOWED_DOMAINS = []         # 严格模式：禁止外网访问
