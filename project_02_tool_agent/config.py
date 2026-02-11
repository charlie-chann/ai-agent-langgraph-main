# config.py — project_02_tool_agent (v2.0)
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field
import os

from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    default_model: str = Field(default="qwen2.5:1.5b", alias="DEFAULT_MODEL")
    temperature: float = Field(default=0.1, alias="TEMPERATURE")
    
    # Search tool
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")
    
    # Code execution
    code_exec_timeout: int = Field(default=10, alias="CODE_EXEC_TIMEOUT")
    
    # Optional: LangSmith
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()


# Legacy exports for backward compatibility
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
TEMPERATURE = settings.temperature
MAX_SEARCH_RESULTS = settings.max_search_results
CODE_EXEC_TIMEOUT = settings.code_exec_timeout
LANGSMITH_ENABLED = settings.langsmith_api_key != ""

# LangSmith setup
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_02_tool_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
