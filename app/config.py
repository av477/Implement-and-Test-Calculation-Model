"""Application settings, read from environment variables (or a local .env file)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg2://appuser:apppassword@localhost:5432/secure_users"
    bcrypt_rounds: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
