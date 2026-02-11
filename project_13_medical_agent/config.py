# config.py — 医疗辅助 Agent 配置
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:1.5b"
TEMPERATURE = 0.1

# 分诊优先级阈值
TRIAGE_EMERGENCY_SCORE = 8   # ≥8 → 立即急诊
TRIAGE_URGENT_SCORE = 5      # 5-7 → 尽快就诊
TRIAGE_ROUTINE_SCORE = 0     # 0-4 → 常规预约

# 隐私与合规
MASK_PII = True              # 脱敏患者个人信息
AUDIT_LOG_ENABLED = True     # 启用操作审计日志

# 知识库路径
SYMPTOM_KB_PATH = "knowledge/symptom_db.json"
APPOINTMENT_SLOTS = 5        # 每个科室每日可用名额
