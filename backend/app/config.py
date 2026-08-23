from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Dict
import os

class Settings(BaseSettings):
    APP_NAME: str = "AuraBrief 95"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Database configuration
    DATABASE_URL: str = "sqlite:///./aurabrief.db"
    
    # CORS origins
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ]
    
    # Default 5-signal ranking weights (must sum to 1.0)
    DEFAULT_WEIGHTS: Dict[str, float] = {
        "severity": 0.30,
        "frequency": 0.20,
        "recency": 0.15,
        "anomaly": 0.20,
        "business_impact": 0.15
    }
    
    # Top N events to attach AI explanations to
    TOP_N_EXPLANATIONS: int = 5
    
    # Gen-AI configuration (Optional Gemini or Ollama)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
