"""
Environment-driven configuration for VB_Converter.

Uses pydantic-settings for type-safe environment variable management.
All deployment-specific settings should be configured via environment
variables or .env file.
"""

from enum import Enum
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    TEST = "test"
    ACCEPTANCE = "acceptance"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    Environment variable names are uppercase versions of the field names.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Application ===
    app_name: str = "VB_Converter"
    app_version: str = "4.2.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True

    # === Security ===
    # SECRET_KEY is required for production. Generate with: openssl rand -hex 32
    secret_key: str = "dev-only-change-in-production-openssl-rand-hex-32"

    # === Server ===
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # CORS - comma-separated list of allowed origins
    allowed_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080,http://localhost:8081,http://localhost:8082,http://localhost:8083,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # === NLP/AI Settings ===
    spacy_model: str = "nl_core_news_md"
    semantic_enabled: bool = True
    embedding_model: str = "intfloat/multilingual-e5-large-instruct"

    # === Logging ===
    log_level: str = "INFO"
    log_format: str = "text"  # "text" for dev, "json" for production

    # === Rate Limiting ===
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds

    # === Feature Flags ===
    feature_ai_extensions: bool = False

    # === Authentication (Fase 1.2) ===
    # Enable/disable JWT auth. Default: False (dev). Set to True in production!
    auth_enabled: bool = False

    # Metrics endpoint token (optional). When set, the /metrics endpoint accepts
    # requests with 'Authorization: Bearer <token>' from non-localhost hosts.
    # Generate with: openssl rand -hex 32
    # If not set, /metrics is restricted to localhost-only access.
    metrics_token: Optional[str] = None

    # JWT settings
    # Token lifetime in minutes (default: 480 = 8 hours)
    jwt_expire_minutes: int = 480

    # Admin credentials (single-user auth for corporate internal tool)
    # Username for the admin account
    admin_username: str = "admin"
    # bcrypt hash of admin password. Generate with:
    #   python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['bcrypt']); print(c.hash('yourpassword'))"
    # If not set: in dev mode, password defaults to 'admin' (NEVER in production!)
    admin_password_hash: Optional[str] = None

    # === Database ===
    # Unified database URL. SQLite is the default so jobs survive server restarts
    # without any extra setup. Override with a PostgreSQL URL for production.
    # Formats:
    #   SQLite (default): sqlite:///./hienfeld_jobs.db
    #   PostgreSQL:       postgresql://user:password@host:port/dbname
    database_url: Optional[str] = "sqlite:///./hienfeld_jobs.db"

    # Legacy per-vendor aliases (kept for backwards compatibility).
    # When set, POSTGRES_URL and SQLITE_URL take precedence over DATABASE_URL.
    postgres_url: Optional[str] = None
    sqlite_url: Optional[str] = None

    # === LLM API (DISABLED) ===
    # External LLM APIs are disabled. All NLP processing is local.
    # openai_api_key: Optional[str] = None  # REMOVED
    # llm_model: str = "gpt-4o-mini"  # REMOVED

    def get_allowed_origins_list(self) -> List[str]:
        """Parse comma-separated origins into list."""
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are loaded once and cached for the lifetime of the application.
    Use this function to access settings throughout the application.

    Returns:
        Settings instance with values from environment
    """
    return Settings()
