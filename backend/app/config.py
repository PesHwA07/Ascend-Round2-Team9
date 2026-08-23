from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
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
    
    # Default ranking weights (must sum to ~1.0)
    DEFAULT_SEVERITY_WEIGHT: float = 0.35
    DEFAULT_BLAST_RADIUS_WEIGHT: float = 0.25
    DEFAULT_ANOMALY_WEIGHT: float = 0.20
    DEFAULT_RECURRENCE_WEIGHT: float = 0.20
    
    # Top N events to attach AI explanations to
    TOP_N_EXPLANATIONS: int = 5
    
    # Gen-AI configuration (Optional Gemini API key)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
