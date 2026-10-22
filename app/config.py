"""Application configuration management using Pydantic Settings."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pipeline and system configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    INPUT_DATA_DIR: Path = BASE_DIR / "data" / "raw"
    SAMPLE_DATA_DIR: Path = BASE_DIR / "data" / "sample"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Database
    DATABASE_URL: str = "sqlite:///clinical_trial.db"

    # Pipeline Meta
    PIPELINE_NAME: str = "clinical-trial-etl"
    PIPELINE_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"

    # API & Dashboard
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    STREAMLIT_PORT: int = 8501


settings = Settings()

# Ensure standard log directory exists
os.makedirs(settings.LOGS_DIR, exist_ok=True)
