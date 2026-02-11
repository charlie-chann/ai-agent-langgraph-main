# config.py — project_06_code_agent
import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:1.5b")
CODE_MODEL: str = os.getenv("CODE_MODEL", "qwen2.5-coder:latest")
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))

# Code execution sandbox
SANDBOX_DIR: str = os.getenv("SANDBOX_DIR", "sandbox_workspace")
CODE_EXEC_TIMEOUT: int = int(os.getenv("CODE_EXEC_TIMEOUT", "10"))
ALLOWED_LANGUAGES = {"python", "bash", "javascript"}

# Git (optional)
GIT_ENABLED: bool = os.getenv("GIT_ENABLED", "false").lower() == "true"

AGENT_MAX_ITERATIONS: int = int(os.getenv("AGENT_MAX_ITERATIONS", "8"))

LANGSMITH_ENABLED: bool = os.getenv("LANGSMITH_API_KEY", "") != ""
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_06_code_agent")
