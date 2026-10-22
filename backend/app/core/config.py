import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "OMNIVEX AI Reliability Monitor"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api"
    DESCRIPTION: str = (
        "Academic research tool for AI reliability monitoring under changing real-world conditions. "
        "Controlled research prototype - not certified for safety-critical production."
    )

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DOCS_ENABLED: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./omnivex.db"

    # Storage paths
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)
    DATA_DIR: Path = Field(default_factory=lambda: Path("./data"))
    UPLOAD_DIR: Path = Field(default_factory=lambda: Path("./data/uploads"))
    MODEL_DIR: Path = Field(default_factory=lambda: Path("./data/models"))
    RESULTS_DIR: Path = Field(default_factory=lambda: Path("./results"))

    # Security & limits
    OMNIVEX_API_KEY: Optional[str] = None
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB streaming limit
    MAX_ROWS: int = 100_000
    MAX_COLUMNS: int = 200
    MAX_FEATURES: int = 100
    MAX_BOOTSTRAP_RESAMPLES: int = 1000
    MAX_EXPERIMENT_REPEATS: int = 10
    PER_RUN_TIME_BUDGET_SECONDS: int = 60

    # Rate limiting
    RATE_LIMIT_DEFAULT: str = "60/minute"
    RATE_LIMIT_STRICT: str = "20/minute"

    # Default statistical and monitoring thresholds
    KS_ALPHA: float = 0.05
    KS_MIN_EFFECT: float = 0.10
    PSI_MODERATE: float = 0.10
    PSI_MAJOR: float = 0.25
    MIN_SAMPLES_DRIFT: int = 30
    MIN_SAMPLES_PERFORMANCE: int = 30
    PERFORMANCE_DROP_TOLERANCE: float = 0.05
    DRIFT_RATIO_THRESHOLD: float = 0.30
    MAX_ALERTS_PER_RUN: int = 20

    def resolve_paths(self) -> None:
        """Resolve storage paths relative to workspace if relative."""
        self.DATA_DIR = self.DATA_DIR.resolve()
        self.UPLOAD_DIR = self.UPLOAD_DIR.resolve()
        self.MODEL_DIR = self.MODEL_DIR.resolve()
        self.RESULTS_DIR = self.RESULTS_DIR.resolve()


settings = Settings()
settings.resolve_paths()
