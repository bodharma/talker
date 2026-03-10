# talker/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://talker:talker@localhost:5432/talker"

    # OpenRouter
    openrouter_api_key: str = ""
    openrouter_model_conversation: str = "anthropic/claude-sonnet-4-20250514"
    openrouter_model_screener: str = "anthropic/claude-haiku-4-20250414"

    # Langfuse
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # App
    app_secret_key: str = "change-me-in-production"
    admin_token: str = "change-me-in-production"
    debug: bool = False
