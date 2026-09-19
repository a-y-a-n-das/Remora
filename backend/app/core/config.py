import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    AWS_REGION: str = Field(default="us-east-1")

    S3_BUCKET: str = Field(default="")

    MAX_FILE_SIZE_MB: int = Field(default=10)
    MAX_FILES_PER_REQUEST: int = Field(default=5)
    RATE_LIMIT_UPLOADS: int = Field(default=20)
    MAX_TOTAL_STORAGE_GB: int = Field(default=10)

    ADMIN_USERNAME: str = Field(default="admin")
    ADMIN_PASSWORD: str = Field(default="")

    ALLOWED_MIME_TYPES: list[str] = Field(
        default=[
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "image/heic",
            "image/heif",
        ]
    )

    PRESIGNED_URL_EXPIRY_SECONDS: int = Field(default=3600)

    ALLOWED_ORIGINS: list[str] = Field(default=["*"])

    # SQS
    SQS_QUEUE_URL: str = Field(default="")
    SQS_MAX_MESSAGES: int = Field(default=1)
    SQS_WAIT_TIME_SECONDS: int = Field(default=20)
    SQS_VISIBILITY_TIMEOUT_SECONDS: int = Field(default=300)

    # Textract
    TEXTRACT_MAX_RETRIES: int = Field(default=3)

    # Bedrock
    BEDROCK_EMBEDDING_MODEL_ID: str = Field(default="amazon.titan-embed-image-v1")
    BEDROCK_EMBEDDING_DIMENSION: int = Field(default=1024)
    BEDROCK_MAX_RETRIES: int = Field(default=3)

    # Neon PostgreSQL
    NEON_DATABASE_URL: str = Field(default="")

    # Voyage AI
    VOYAGE_API_KEY: str = Field(default="")
    VOYAGE_MODEL: str = Field(default="voyage-multimodal-3")
    VOYAGE_EMBEDDING_DIMENSION: int = Field(default=1024)
    VOYAGE_MAX_RETRIES: int = Field(default=3)
    VOYAGE_TIMEOUT_SECONDS: float = Field(default=30.0)

    # S3 Vectors
    S3_VECTORS_BUCKET: str = Field(default="")
    S3_VECTORS_INDEX: str = Field(default="memories")
    S3_VECTORS_DIMENSION: int = Field(default=1024)
    S3_VECTORS_DISTANCE_METRIC: str = Field(default="cosine")
    S3_VECTORS_MAX_RETRIES: int = Field(default=3)

    LOG_LEVEL: str = Field(default="INFO")

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()