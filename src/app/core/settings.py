from enum import Enum

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    NONE = "none"
    GROQ = "groq"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_ignore_empty=True, extra="ignore"
    )

    # Database Components
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "arxiv_insight"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Application
    DEBUG: bool = False
    ENVIRONMENT: str = "local"
    LOG_LEVEL: str = "INFO"

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "arXiv Insight API"
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: list[str] = ["*"]

    # Ingestion
    ARXIV_API_URL: str = "https://export.arxiv.org/api/query"
    INGESTION_RATE_LIMIT: float = 3.1  # seconds between requests

    # LLM & Embeddings (Strictly validated)
    LLM_PROVIDER: LLMProvider = LLMProvider.NONE
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str | None = None

    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384

    @field_validator("LLM_API_KEY")
    @classmethod
    def validate_llm_key(cls, v: str | None, info: ValidationInfo) -> str | None:
        provider = info.data.get("LLM_PROVIDER", LLMProvider.NONE)
        if provider != LLMProvider.NONE and not v:
            raise ValueError(
                f"LLM_API_KEY is absolutely required when LLM_PROVIDER is '{provider.value}'"
            )
        return v

settings = Settings()  # type: ignore
