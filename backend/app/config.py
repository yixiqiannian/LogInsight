import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Settings:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./loginsight.db")

    LLM_API_TYPE: str = os.getenv("LLM_API_TYPE", "openai_compatible")
    LLM_API_BASE: str = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo")

    LOG_RETENTION_DAYS_INFO: int = int(os.getenv("LOG_RETENTION_DAYS_INFO", "7"))
    LOG_RETENTION_DAYS_WARN: int = int(os.getenv("LOG_RETENTION_DAYS_WARN", "30"))
    LOG_RETENTION_DAYS_ERROR: int = int(os.getenv("LOG_RETENTION_DAYS_ERROR", "90"))
    DEBUG_LOG_PERSIST: bool = os.getenv("DEBUG_LOG_PERSIST", "false").lower() == "true"

    CONTEXT_WINDOW_MINUTES: int = int(os.getenv("CONTEXT_WINDOW_MINUTES", "5"))
    AUTO_ANALYZE_ERROR: bool = os.getenv("AUTO_ANALYZE_ERROR", "true").lower() == "true"
    MAX_ANALYSIS_QUEUE_SIZE: int = int(os.getenv("MAX_ANALYSIS_QUEUE_SIZE", "100"))

    FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")

    BATCH_WRITE_SIZE: int = 100
    BATCH_WRITE_INTERVAL: float = 1.0


settings = Settings()
