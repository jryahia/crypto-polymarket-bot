"""Application configuration via Pydantic Settings."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from cryptography.fernet import Fernet
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "staging", "production"] = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Security
    encryption_key: str = Field(default="")
    secret_key: str = Field(default="changeme_32_chars_long_secret!!")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/db/aether.db"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"
    chroma_host: str = ""  # If set, use HTTP client instead of local

    # LLM
    llm_primary_provider: Literal["openai", "anthropic"] = "openai"
    llm_fallback_provider: Literal["openai", "anthropic"] = "anthropic"
    llm_primary_model: str = "gpt-4o"
    llm_fallback_model: str = "claude-3-5-sonnet-20241022"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096

    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # Binance
    binance_api_key: str = Field(default="")
    binance_api_secret: str = Field(default="")
    binance_testnet: bool = True

    # Polymarket
    polymarket_private_key: str = Field(default="")
    polymarket_api_key: str = Field(default="")
    polymarket_api_secret: str = Field(default="")
    polymarket_clob_url: str = "https://clob.polymarket.com"
    polymarket_chain_id: int = 137

    # Web3 / On-chain
    ethereum_rpc_url: str = Field(default="")
    polygon_rpc_url: str = Field(default="")
    etherscan_api_key: str = Field(default="")
    monitored_wallets: str = Field(default="")

    # News / Research
    cryptopanic_api_key: str = Field(default="")
    news_api_key: str = Field(default="")

    # Notifications
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    alert_email: str = Field(default="")

    # Brain cycle
    brain_cycle_interval_seconds: int = 300
    confidence_threshold: float = 0.65
    max_position_size_usd: float = 1000.0
    daily_loss_limit_usd: float = 500.0
    enable_live_trading: bool = False

    @field_validator("encryption_key", mode="before")
    @classmethod
    def _set_encryption_key(cls, v: str) -> str:
        if not v:
            return Fernet.generate_key().decode()
        return v

    def get_fernet(self) -> Fernet:
        key = self.encryption_key.encode() if isinstance(self.encryption_key, str) else self.encryption_key
        # Pad/encode to valid Fernet key if necessary
        try:
            return Fernet(key)
        except Exception:
            new_key = Fernet.generate_key()
            return Fernet(new_key)

    def encrypt_value(self, value: str) -> str:
        return self.get_fernet().encrypt(value.encode()).decode()

    def decrypt_value(self, token: str) -> str:
        return self.get_fernet().decrypt(token.encode()).decode()

    @property
    def monitored_wallet_list(self) -> list[str]:
        if not self.monitored_wallets:
            return []
        return [w.strip() for w in self.monitored_wallets.split(",") if w.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def soul_profile_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "soul", "profile.json")

    @property
    def skills_dir(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")


@lru_cache
def get_settings() -> Settings:
    return Settings()
