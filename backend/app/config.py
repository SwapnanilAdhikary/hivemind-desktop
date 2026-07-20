from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM providers
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    default_llm_provider: str = "ollama"
    default_model_name: str = "llama3"

    # Gmail
    gmail_credentials_path: str = "credentials/gmail_credentials.json"
    gmail_token_path: str = "credentials/gmail_token.json"

    # Discord
    discord_bot_token: str = ""

    # Instagram
    instagram_username: str = ""
    instagram_password: str = ""

    # Server
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    redis_url: str = "redis://localhost:6379/0"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/agent_platform.db"

    # WhatsApp bridge
    whatsapp_bridge_url: str = "ws://127.0.0.1:8001"


settings = Settings()
