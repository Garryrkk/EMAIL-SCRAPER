import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    ENVIRONMENT: str = Field(default="dev", validation_alias="APP_ENV")
    DEBUG: bool = Field(default=False)
    PORT: int = Field(default=8000)

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:garima123@localhost:5432/emailscraper",
        validation_alias="DATABASE_URL",
    )
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=10)
    DB_POOL_RECYCLE: int = Field(default=3600)

    # Security
    SECRET_KEY: str = Field(default="dev-secret-key-change-in-prod")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRY_MINUTES: int = Field(default=60)
    JWT_REFRESH_EXPIRY_DAYS: int = Field(default=7)

    # CORS & Hosts
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"]
    )
    ALLOWED_HOSTS: List[str] = Field(default=["*"])

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_REQUESTS: int = Field(default=100)
    RATE_LIMIT_PERIOD_SECONDS: int = Field(default=60)

    # Email
    SMTP_HOST: str = Field(default="smtp.gmail.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM: str = Field(default="noreply@apollo.com")
    SMTP_TIMEOUT: int = Field(default=10)

    # Crawling
    CRAWLER_USER_AGENT: str = Field(
        default="Mozilla/5.0 (compatible; ApolloBot/1.0)"
    )
    CRAWLER_TIMEOUT: int = Field(default=10)
    CRAWLER_MAX_RETRIES: int = Field(default=3)
    CRAWLER_RATE_LIMIT_PER_DOMAIN: int = Field(default=2)  # requests per second

    # DNS
    DNS_TIMEOUT: int = Field(default=5)
    DNS_RETRIES: int = Field(default=2)

    # SMTP Verification
    SMTP_VERIFICATION_ENABLED: bool = Field(default=True)
    SMTP_VERIFY_TIMEOUT: int = Field(default=30)

    # Feature Flags
    FEATURE_ENRICHMENT_ENABLED: bool = Field(default=True)
    FEATURE_VERIFICATION_ENABLED: bool = Field(default=True)
    FEATURE_BULK_SEARCH_ENABLED: bool = Field(default=True)

    # External APIs
    CLEARBIT_API_KEY: str = Field(default="")
    PDL_API_KEY: str = Field(default="")
    CRUNCHBASE_API_KEY: str = Field(default="")

    # Redis (for caching and rate limiting)
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Search
    ELASTICSEARCH_URL: str = Field(default="http://localhost:9200")

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FILE: str = Field(default="logs/apollo.log")

    # Workers
    WORKER_PROCESSES: int = Field(default=4)
    TASK_QUEUE_SIZE: int = Field(default=1000)

    # Abuse Detection
    ABUSE_DETECTION_ENABLED: bool = Field(default=True)
    RISK_SCORE_THRESHOLD: float = Field(default=0.7)

    # GDPR
    GDPR_ENABLED: bool = Field(default=True)
    DATA_RETENTION_DAYS: int = Field(default=90)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()