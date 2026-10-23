from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"

    # Database - Supabase PostgreSQL
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str

    # Firebase Authentication
    FIREBASE_PROJECT_ID: str
    FIREBASE_CLIENT_EMAIL: str
    FIREBASE_PRIVATE_KEY: str

    # AI Configuration (Stage 4)
    AI_PROVIDER: str = "gemini"
    AI_PROMPT_VERSION: str = "security-finding-analysis-v1"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    GROK_API_KEY: Optional[str] = None
    GROK_MODEL: str = "grok-1"
    AI_MAX_FINDINGS_PER_RUN: int = 10
    AI_MAX_INPUT_CHARS: int = 50000
    AI_MAX_OUTPUT_TOKENS: int = 4096
    AI_TIMEOUT_SECONDS: int = 60
    AI_MAX_RETRIES: int = 3
    AI_DAILY_ANALYSIS_LIMIT: int = 100

    # Redis (for Celery, caching, rate limiting)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # n8n
    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_API_KEY: Optional[str] = None

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Scan Configuration (Stage 3)
    SCAN_WORKSPACE_ROOT: str = "/scan-workspace"
    SEMGREP_BINARY: str = "semgrep"
    SEMGREP_VERSION: str = "1.45.0"
    SCAN_TIMEOUT_SECONDS: int = 1800
    SCAN_PREP_TIMEOUT_SECONDS: int = 300
    SCAN_PARSE_TIMEOUT_SECONDS: int = 120
    MAX_SCAN_TARGET_SIZE_MB: int = 1000
    MAX_FILE_SIZE_MB: int = 10
    MAX_CONCURRENT_SCANS_PER_WORKSPACE: int = 3
    SCAN_BUDGET_DEFAULT_USD: float = 10.0
    SCAN_DEFAULT_PROFILE: str = "CODE_SECURITY"
    SEMGREP_RULESETS: str = "p/security-audit,p/secrets,p/owasp-top-ten"
    SCAN_PREP_TIMEOUT_SECONDS: int = 300
    SCAN_PARSE_TIMEOUT_SECONDS: int = 120

    # Worker Configuration (Stage 12A - Scanner Isolation)
    WORKER_SCAN_TIMEOUT: int = 1800
    WORKER_MAX_TARGET_SIZE_MB: int = 1000
    WORKER_MAX_FILE_SIZE_MB: int = 10
    WORKER_SEMGREP_TIMEOUT: int = 1800

    # Logging
    LOG_LEVEL: str = "INFO"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins(self) -> list[str]:
        if self.is_production:
            return [self.FRONTEND_URL]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]


settings = Settings()