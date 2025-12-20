from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, field_validator
import json


class Settings(BaseSettings):
    # Application Settings
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Mochi Donut"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Security
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    def __init__(self, **kwargs):
        """Initialize settings with validation."""
        super().__init__(**kwargs)
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY environment variable is required. "
                "Please set it in your .env file. "
                "See .env.sample for an example. "
                "For development, you can generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./mochi_donut.db"

    # API Keys
    OPENAI_API_KEY: Optional[str] = None
    MOCHI_API_KEY: Optional[str] = None
    JINA_API_KEY: Optional[str] = None

    # Chroma Configuration
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_API_KEY: Optional[str] = None
    CHROMA_COLLECTION_PREFIX: str = "mochi_donut"

    # CORS Configuration
    CORS_ORIGINS: List[str] = ["http://localhost:8000"]

    @field_validator("CORS_ORIGINS", mode="before")
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("["):
                return json.loads(v)
            return [i.strip() for i in v.split(",")]
        return v

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    # AI Model Configuration
    AI_CACHING_ENABLED: bool = True
    DEFAULT_AI_MODEL: str = "gpt-5-nano"
    QUALITY_REVIEW_MODEL: str = "gpt-5-standard"
    PROMPT_GENERATION_MODEL: str = "gpt-5-mini"

    # AI Model Costs (per 1M tokens, 2025 pricing)
    GPT5_NANO_INPUT_COST: float = 0.05
    GPT5_NANO_OUTPUT_COST: float = 0.40
    GPT5_MINI_INPUT_COST: float = 0.25
    GPT5_MINI_OUTPUT_COST: float = 2.00
    GPT5_STANDARD_INPUT_COST: float = 1.25
    GPT5_STANDARD_OUTPUT_COST: float = 10.00

    # Processing Settings
    MAX_CONTENT_LENGTH: int = 100000  # characters
    MIN_PROMPTS_PER_CONTENT: int = 5
    MAX_PROMPTS_PER_CONTENT: int = 20
    QUALITY_THRESHOLD: float = 0.7

    # External Service Configuration
    JINA_API_TIMEOUT: int = 30  # seconds
    JINA_CACHE_ENABLED: bool = True
    JINA_CACHE_TTL: int = 86400  # 24 hours

    MOCHI_API_TIMEOUT: int = 30  # seconds
    MOCHI_RATE_LIMIT_DELAY: float = 0.5  # seconds between requests
    MOCHI_MAX_CONCURRENT_REQUESTS: int = 3

    CHROMA_TIMEOUT: int = 30  # seconds
    CHROMA_SIMILARITY_THRESHOLD: float = 0.7
    CHROMA_MAX_RESULTS: int = 100

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()