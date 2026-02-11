# config.py — Browser Automation Agent configuration
import os
from dotenv import load_dotenv

load_dotenv()

# ── Ollama ──────────────────────────────────────────────────────────────────
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
CREATIVE_TEMPERATURE: float = float(os.getenv("CREATIVE_TEMPERATURE", "0.7"))

# ── Browser ─────────────────────────────────────────────────────────────────
BROWSER_HEADLESS: bool = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
BROWSER_MAX_STEPS: int = int(os.getenv("BROWSER_MAX_STEPS", "20"))
SCREENSHOT_DIR: str = os.getenv("SCREENSHOT_DIR", "screenshots")

# ── Playwright ───────────────────────────────────────────────────────────────
# Simulated mode: uses requests+BeautifulSoup (no Playwright required for tests)
USE_PLAYWRIGHT: bool = os.getenv("USE_PLAYWRIGHT", "false").lower() == "true"

# ── API ─────────────────────────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8009"))

# ── LangSmith (optional) ─────────────────────────────────────────────────────
LANGCHAIN_TRACING_V2: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "browser-agent")
