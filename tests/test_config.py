"""Unit tests for MARIA configuration management."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from maria.config import Settings, get_settings


def test_default_settings():
    """Verify default settings values when no environment variables are set."""
    settings = Settings(_env_file=None)

    assert settings.env == "development"
    assert settings.log_level == "INFO"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.data_dir == Path.home() / ".maria"
    assert settings.db_path == Path.home() / ".maria" / "maria.db"
    assert settings.master_key is None
    assert settings.gemini_api_key is None
    assert settings.openai_api_key is None
    assert settings.anthropic_api_key is None
    assert settings.openrouter_api_key is None
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.is_development is True
    assert settings.is_production is False
    assert settings.is_testing is False


def test_environment_normalization():
    """Environment strings should be normalized to lowercase."""
    settings_dev = Settings(env="DEVELOPMENT", _env_file=None)
    assert settings_dev.env == "development"
    assert settings_dev.is_development is True

    settings_prod = Settings(env="Production", _env_file=None)
    assert settings_prod.env == "production"
    assert settings_prod.is_production is True

    settings_test = Settings(env="TESTING", _env_file=None)
    assert settings_test.env == "testing"
    assert settings_test.is_testing is True


def test_invalid_environment_raises():
    """Invalid environment values should raise a ValidationError."""
    with pytest.raises(ValidationError):
        Settings(env="staging", _env_file=None)


def test_log_level_normalization():
    """Log level strings should be normalized to uppercase."""
    settings = Settings(log_level="debug", _env_file=None)
    assert settings.log_level == "DEBUG"

    settings_warn = Settings(log_level="warning", _env_file=None)
    assert settings_warn.log_level == "WARNING"


def test_invalid_log_level_raises():
    """Invalid log level values should raise a ValidationError."""
    with pytest.raises(ValidationError):
        Settings(log_level="VERBOSE", _env_file=None)


def test_port_validation():
    """Port numbers must be between 1 and 65535."""
    valid_settings = Settings(port=8080, _env_file=None)
    assert valid_settings.port == 8080

    with pytest.raises(ValidationError):
        Settings(port=0, _env_file=None)

    with pytest.raises(ValidationError):
        Settings(port=65536, _env_file=None)


def test_path_expansion():
    """Tilde in path should expand to the user's home directory."""
    settings = Settings(data_dir=Path("~/.maria_test"), _env_file=None)
    assert "~" not in str(settings.data_dir)
    assert settings.data_dir == Path.home() / ".maria_test"
    assert settings.db_path == Path.home() / ".maria_test" / "maria.db"


def test_custom_db_path():
    """Explicit db_path should override the default db_path."""
    custom_db = Path("~/.maria_test/custom.db")
    settings = Settings(db_path=custom_db, _env_file=None)
    assert settings.db_path == Path.home() / ".maria_test" / "custom.db"


def test_secret_str_masking():
    """API keys must never be exposed via str() or repr()."""
    test_key = "test-secret-key-12345"
    settings = Settings(gemini_api_key=test_key, _env_file=None)

    assert settings.gemini_api_key is not None
    # String representation must be masked
    assert test_key not in str(settings.gemini_api_key)
    assert test_key not in repr(settings.gemini_api_key)
    assert "**********" in str(settings.gemini_api_key)

    # Actual value accessible only via get_secret_value()
    assert settings.gemini_api_key.get_secret_value() == test_key


def test_configured_providers():
    """configured_providers() should accurately report available providers."""
    empty_settings = Settings(ollama_base_url="", _env_file=None)
    assert empty_settings.configured_providers() == []

    configured = Settings(
        gemini_api_key="gem-key",
        openai_api_key="oai-key",
        anthropic_api_key="claude-key",
        openrouter_api_key="router-key",
        ollama_base_url="http://localhost:11434",
        _env_file=None,
    )
    providers = configured.configured_providers()
    assert "gemini" in providers
    assert "openai" in providers
    assert "anthropic" in providers
    assert "openrouter" in providers
    assert "ollama" in providers


def test_env_file_loading(tmp_path):
    """Settings should load values correctly from an environment file."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "MARIA_ENV=production\n"
        "MARIA_PORT=9000\n"
        "MARIA_LOG_LEVEL=DEBUG\n"
        "GEMINI_API_KEY=env-gemini-key\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=str(env_file))
    assert settings.env == "production"
    assert settings.port == 9000
    assert settings.log_level == "DEBUG"
    assert settings.gemini_api_key is not None
    assert settings.gemini_api_key.get_secret_value() == "env-gemini-key"


def test_monkeypatch_environment_variables(monkeypatch):
    """Settings should respect OS environment variable overrides."""
    monkeypatch.setenv("MARIA_ENV", "testing")
    monkeypatch.setenv("MARIA_HOST", "0.0.0.0")
    monkeypatch.setenv("MARIA_PORT", "8888")
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")

    settings = Settings(_env_file=None)
    assert settings.env == "testing"
    assert settings.is_testing is True
    assert settings.host == "0.0.0.0"
    assert settings.port == 8888
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "env-openai-key"


def test_get_settings_caching():
    """get_settings() should return a cached singleton instance."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
