import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_ID: str = "SP-002"
    PROJECT_TITLE: str = "Online Course Registration Portal"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sp002-dev-secret-key-change-in-prod-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    # Defaults to SQLite for zero-config instant local execution; set DATABASE_URL for PostgreSQL
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sp002_portal.db")


settings = Settings()
