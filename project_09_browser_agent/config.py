# config.py — Browser Automation Agent 全局配置
#
# 【职责】集中管理 LLM 连接、浏览器行为、API 端口等运行参数。
# 所有模块通过 import 本文件获取配置，部署时可用 .env 覆盖默认值。
import os
from dotenv import load_dotenv

load_dotenv()  # 加载 .env 文件中的环境变量

# ── Ollama LLM 连接 ─────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")  # Ollama 服务地址
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")               # 默认推理模型
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))                  # 规划阶段温度（偏确定性）
CREATIVE_TEMPERATURE: float = float(os.getenv("CREATIVE_TEMPERATURE", "0.7"))  # 报告生成温度（预留）

# ── 浏览器行为 ───────────────────────────────────────────────────────────────
BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"  # 无头模式（Playwright）
BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))           # 单次 HTTP 请求超时（毫秒）
BROWSER_MAX_STEPS: int = int(os.getenv("BROWSER_MAX_STEPS", "20"))                # ReAct 最大循环步数，防死循环
SCREENSHOT_DIR: str = os.getenv("SCREENSHOT_DIR", "screenshots")                  # 截图保存目录

# ── Playwright 模式开关 ─────────────────────────────────────────────────────
# 默认 false：用 requests+BeautifulSoup 抓静态页（无需安装浏览器，测试友好）
# 设为 true：启用真实无头浏览器，支持 JS 渲染页面
USE_PLAYWRIGHT: bool = os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"

# ── FastAPI 服务 ─────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")   # API 监听地址
API_PORT: int = int(os.getenv("API_PORT", "8009"))  # API 端口

# ── LangSmith 链路追踪（可选）────────────────────────────────────────────────
LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "browser-agent")
