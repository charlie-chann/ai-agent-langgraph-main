# config.py — project_03_multi_agent (v2.0)
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
    creative_temperature: float = Field(default=0.7, alias="CREATIVE_TEMPERATURE")
    
    # Agent settings
    max_revision_loops: int = Field(default=2, alias="MAX_REVISION_LOOPS")
    critic_pass_score: int = Field(default=7, alias="CRITIC_PASS_SCORE")
    
    # Search
    max_search_results: int = Field(default=5, alias="MAX_SEARCH_RESULTS")
    
    # LangSmith (optional)
    langsmith_api_key: str = Field(default="", alias="LANGSMITH_API_KEY")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()


# Legacy exports
OLLAMA_BASE_URL = settings.ollama_base_url
DEFAULT_MODEL = settings.default_model
TEMPERATURE = settings.temperature
CREATIVE_TEMPERATURE = settings.creative_temperature
MAX_REVISION_LOOPS = settings.max_revision_loops
CRITIC_PASS_SCORE = settings.critic_pass_score
MAX_SEARCH_RESULTS = settings.max_search_results
LANGSMITH_ENABLED = settings.langsmith_api_key != ""

# Supported scenarios
SCENARIO_MARKET_RESEARCH = "market_research"
SCENARIO_SOCIAL_MEDIA = "social_media"

# LangSmith setup
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", "project_03_multi_agent")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
