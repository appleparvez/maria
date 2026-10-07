"""MARIA configuration management.

Configuration is loaded from environment variables and an optional .env file.
Sensitive values (API keys, master keys) are wrapped in SecretStr so they are
never exposed in logs, exceptions, or string representations.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvironmentType = Literal["development", "testing", "production"]
LogLevelType = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """MARIA application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core Application Settings ---
    env: EnvironmentType = Field(
        default="development",
        validation_alias=AliasChoices("MARIA_ENV", "env"),
        description="Application running environment.",
    )
    log_level: LogLevelType = Field(
        default="INFO",
        validation_alias=AliasChoices("MARIA_LOG_LEVEL", "log_level"),
        description="Application logging verbosity.",
    )
    host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("MARIA_HOST", "host"),
        description="Bind host for API server.",
    )
    port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        validation_alias=AliasChoices("MARIA_PORT", "port"),
        description="Port for API server.",
    )

    # --- Storage & Paths ---
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".maria",
        validation_alias=AliasChoices("MARIA_DATA_DIR", "data_dir"),
        description="Root directory for local data, credentials, and audit logs.",
    )
    db_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("MARIA_DB_PATH", "db_path"),
        description="Path to SQLite database file. Defaults to data_dir / maria.db.",
    )

    # --- Security & Credentials ---
    master_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("MARIA_MASTER_KEY", "master_key"),
        description="Optional master key for credential vault encryption.",
    )

    # --- AI Provider API Keys (BYOK - Bring Your Own Key) ---
    gemini_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "MARIA_GEMINI_API_KEY", "gemini_api_key"),
        description="Google Gemini API key.",
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "MARIA_OPENAI_API_KEY", "openai_api_key"),
        description="OpenAI API key.",
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ANTHROPIC_API_KEY", "MARIA_ANTHROPIC_API_KEY", "anthropic_api_key"
        ),
        description="Anthropic Claude API key.",
    )
    openrouter_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "OPENROUTER_API_KEY", "MARIA_OPENROUTER_API_KEY", "openrouter_api_key"
        ),
        description="OpenRouter API key.",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices(
            "OLLAMA_BASE_URL", "MARIA_OLLAMA_BASE_URL", "ollama_base_url"
        ),
        description="Ollama local instance base URL.",
    )

    @field_validator("env", mode="before")
    @classmethod
    def _normalize_env(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("data_dir", "db_path", mode="after")
    @classmethod
    def _expand_path(cls, v: Path | None) -> Path | None:
        if v is not None:
            return v.expanduser()
        return v

    @model_validator(mode="after")
    def _set_default_db_path(self) -> Self:
        if self.db_path is None:
            self.db_path = self.data_dir / "maria.db"
        return self

    @property
    def is_development(self) -> bool:
        """Return True if running in development mode."""
        return self.env == "development"

    @property
    def is_production(self) -> bool:
        """Return True if running in production mode."""
        return self.env == "production"

    @property
    def is_testing(self) -> bool:
        """Return True if running in testing mode."""
        return self.env == "testing"

    def configured_providers(self) -> list[str]:
        """Return a list of provider names that have credentials or endpoints configured."""
        providers: list[str] = []
        if self.gemini_api_key is not None:
            providers.append("gemini")
        if self.openai_api_key is not None:
            providers.append("openai")
        if self.anthropic_api_key is not None:
            providers.append("anthropic")
        if self.openrouter_api_key is not None:
            providers.append("openrouter")
        if self.ollama_base_url:
            providers.append("ollama")
        return providers


@functools.lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
