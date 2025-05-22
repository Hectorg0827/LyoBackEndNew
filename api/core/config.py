"""
Configuration module for the application.

This module defines settings for the application using Pydantic Settings.
"""
from typing import List, Optional, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application settings
    APP_NAME: str = "lyo-backend"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Security settings
    SECRET_KEY: str = Field(..., description="Secret key for JWT")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # CORS settings
    CORS_ORIGINS: List[str] = ["*"]
    
    # Rate limiting settings
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_DAY: int = 10000
    RATE_LIMIT_WHITELIST: List[str] = ["/api/v1/health", "/api/v1/docs", "/api/v1/redoc", "/api/v1/openapi.json"]
    ADMIN_IPS: List[str] = []
    
    # Database settings
    FIRESTORE_PROJECT_ID: Optional[str] = None
    FIRESTORE_EMULATOR_HOST: Optional[str] = None
    
    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_SSL: bool = False
    
    # Cloud SQL (PostgreSQL) settings
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "lyo"
    POSTGRES_SCHEMA: str = "public"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # Pub/Sub settings
    PUBSUB_PROJECT_ID: Optional[str] = None
    PUBSUB_EMULATOR_HOST: Optional[str] = None
    
    # Storage settings
    STORAGE_BUCKET_NAME: str = "lyo-media"
    
    # Avatar AI service settings
    AVATAR_SERVICE_URL: str = "localhost:50051"  # gRPC service address
    
    # External API settings
    GOOGLE_BOOKS_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    
    # Logging and telemetry
    LOG_LEVEL: str = "INFO"
    OTLP_ENDPOINT: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    @field_validator("SQLALCHEMY_DATABASE_URI", mode="after")
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        """Assemble PostgreSQL connection string if not provided."""
        if isinstance(v, str):
            return v
            
        postgres_user = info.data.get("POSTGRES_USER")
        postgres_password = info.data.get("POSTGRES_PASSWORD")
        postgres_server = info.data.get("POSTGRES_SERVER")
        postgres_port = info.data.get("POSTGRES_PORT")
        postgres_db = info.data.get("POSTGRES_DB")
        
        return f"postgresql+psycopg://{postgres_user}:{postgres_password}@{postgres_server}:{postgres_port}/{postgres_db}"


# Create a global settings object
settings = Settings()
