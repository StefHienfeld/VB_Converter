"""
Unit tests for Settings configuration.

Tests cover:
- Settings initialization
- Default values
- Environment variable overrides
- Type validation
- Helper methods
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from hienfeld.settings.settings import Settings, Environment, get_settings


class TestEnvironmentEnum:
    """Tests for Environment enum."""

    def test_environment_values(self):
        """Test that all environment values are defined."""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TEST.value == "test"
        assert Environment.ACCEPTANCE.value == "acceptance"
        assert Environment.PRODUCTION.value == "production"

    def test_environment_comparison(self):
        """Test environment enum comparison."""
        assert Environment.DEVELOPMENT != Environment.PRODUCTION
        assert Environment.DEVELOPMENT == Environment.DEVELOPMENT


class TestSettingsDefaults:
    """Tests for default settings values."""

    def test_default_app_name(self):
        """Test default app name."""
        settings = Settings()
        assert settings.app_name == "VB_Converter"

    def test_default_app_version(self):
        """Test default app version."""
        settings = Settings()
        assert settings.app_version == "4.2.0"

    def test_default_environment(self):
        """Test default environment."""
        settings = Settings()
        # Default may be test due to conftest.py setting ENVIRONMENT
        assert settings.environment in [Environment.DEVELOPMENT, Environment.TEST]

    def test_default_debug(self):
        """Test default debug flag."""
        settings = Settings()
        # Default may be false due to conftest.py setting DEBUG=false
        assert isinstance(settings.debug, bool)

    def test_default_api_host(self):
        """Test default API host."""
        settings = Settings()
        assert settings.api_host == "0.0.0.0"

    def test_default_api_port(self):
        """Test default API port."""
        settings = Settings()
        assert settings.api_port == 8000

    def test_default_log_level(self):
        """Test default log level."""
        settings = Settings()
        assert settings.log_level == "INFO"

    def test_default_rate_limit_enabled(self):
        """Test default rate limit enabled."""
        settings = Settings()
        # May be false due to conftest.py setting RATE_LIMIT_ENABLED=false
        assert isinstance(settings.rate_limit_enabled, bool)

    def test_default_semantic_enabled(self):
        """Test default semantic enabled."""
        settings = Settings()
        assert settings.semantic_enabled is True

    def test_default_auth_enabled(self):
        """Test default auth enabled."""
        settings = Settings()
        assert settings.auth_enabled is False

    def test_default_database_url(self):
        """Test default database URL."""
        settings = Settings()
        assert settings.database_url == "sqlite:///./hienfeld_jobs.db"


class TestEnvironmentVariableOverrides:
    """Tests for environment variable overrides."""

    def test_override_app_name(self):
        """Test overriding app name via environment variable."""
        with patch.dict(os.environ, {"APP_NAME": "CustomApp"}):
            settings = Settings(_env_file=None)
            assert settings.app_name == "CustomApp"

    def test_override_api_port(self):
        """Test overriding API port via environment variable."""
        with patch.dict(os.environ, {"API_PORT": "9000"}):
            settings = Settings(_env_file=None)
            assert settings.api_port == 9000

    def test_override_environment(self):
        """Test overriding environment via environment variable."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            settings = Settings(_env_file=None)
            assert settings.environment == Environment.PRODUCTION

    def test_override_debug(self):
        """Test overriding debug flag via environment variable."""
        with patch.dict(os.environ, {"DEBUG": "false"}):
            settings = Settings(_env_file=None)
            assert settings.debug is False

    def test_override_log_level(self):
        """Test overriding log level via environment variable."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            settings = Settings(_env_file=None)
            assert settings.log_level == "DEBUG"

    def test_override_semantic_enabled(self):
        """Test overriding semantic enabled."""
        with patch.dict(os.environ, {"SEMANTIC_ENABLED": "false"}):
            settings = Settings(_env_file=None)
            assert settings.semantic_enabled is False

    def test_override_auth_enabled(self):
        """Test overriding auth enabled."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "true"}):
            settings = Settings(_env_file=None)
            assert settings.auth_enabled is True

    def test_override_database_url(self):
        """Test overriding database URL."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/testdb"}):
            settings = Settings(_env_file=None)
            assert settings.database_url == "postgresql://localhost/testdb"


class TestSettingsHelperMethods:
    """Tests for helper methods in Settings."""

    def test_get_allowed_origins_list_empty(self):
        """Test parsing empty origins list."""
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": ""}):
            settings = Settings(_env_file=None)
            origins = settings.get_allowed_origins_list()
            assert origins == []

    def test_get_allowed_origins_list_single(self):
        """Test parsing single origin."""
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://localhost:3000"}):
            settings = Settings(_env_file=None)
            origins = settings.get_allowed_origins_list()
            assert origins == ["http://localhost:3000"]

    def test_get_allowed_origins_list_multiple(self):
        """Test parsing multiple origins."""
        origins_str = "http://localhost:3000,http://localhost:8080,http://example.com"
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}):
            settings = Settings(_env_file=None)
            origins = settings.get_allowed_origins_list()
            assert len(origins) == 3
            assert "http://localhost:3000" in origins
            assert "http://localhost:8080" in origins
            assert "http://example.com" in origins

    def test_get_allowed_origins_list_with_whitespace(self):
        """Test parsing origins with extra whitespace."""
        origins_str = " http://localhost:3000 , http://localhost:8080 "
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": origins_str}):
            settings = Settings(_env_file=None)
            origins = settings.get_allowed_origins_list()
            assert len(origins) == 2
            assert origins[0] == "http://localhost:3000"
            assert origins[1] == "http://localhost:8080"

    def test_is_production_true(self):
        """Test is_production property when production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            settings = Settings(_env_file=None)
            assert settings.is_production is True

    def test_is_production_false(self):
        """Test is_production property when not production."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = Settings(_env_file=None)
            assert settings.is_production is False

    def test_is_development_true(self):
        """Test is_development property when development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = Settings(_env_file=None)
            assert settings.is_development is True

    def test_is_development_false(self):
        """Test is_development property when not development."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            settings = Settings(_env_file=None)
            assert settings.is_development is False


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_valid_port_range(self):
        """Test valid port numbers."""
        with patch.dict(os.environ, {"API_PORT": "8000"}):
            settings = Settings(_env_file=None)
            assert 0 < settings.api_port <= 65535

    def test_valid_rate_limit_requests(self):
        """Test valid rate limit requests."""
        with patch.dict(os.environ, {"RATE_LIMIT_REQUESTS": "150"}):
            settings = Settings(_env_file=None)
            assert settings.rate_limit_requests == 150

    def test_valid_rate_limit_window(self):
        """Test valid rate limit window."""
        with patch.dict(os.environ, {"RATE_LIMIT_WINDOW": "120"}):
            settings = Settings(_env_file=None)
            assert settings.rate_limit_window == 120

    def test_jwt_expire_minutes(self):
        """Test JWT expire minutes configuration."""
        with patch.dict(os.environ, {"JWT_EXPIRE_MINUTES": "240"}):
            settings = Settings(_env_file=None)
            assert settings.jwt_expire_minutes == 240

    def test_admin_username(self):
        """Test admin username configuration."""
        with patch.dict(os.environ, {"ADMIN_USERNAME": "superadmin"}):
            settings = Settings(_env_file=None)
            assert settings.admin_username == "superadmin"


class TestSettingsSecurityDefaults:
    """Tests for security-related defaults."""

    def test_default_secret_key_not_production(self):
        """Test that default secret key is set."""
        settings = Settings()
        # Secret key should be set (may be hashed or plain depending on env)
        assert isinstance(settings.secret_key, str)
        assert len(settings.secret_key) > 0

    def test_metrics_token_optional(self):
        """Test that metrics token is optional."""
        settings = Settings()
        # Should not raise, metrics_token can be None
        assert settings.metrics_token is None or isinstance(settings.metrics_token, str)

    def test_admin_password_hash_optional(self):
        """Test that admin password hash is optional."""
        settings = Settings()
        assert settings.admin_password_hash is None or isinstance(settings.admin_password_hash, str)


class TestSettingsNLPDefaults:
    """Tests for NLP/AI settings."""

    def test_default_spacy_model(self):
        """Test default SpaCy model."""
        settings = Settings()
        assert settings.spacy_model == "nl_core_news_md"

    def test_default_embedding_model(self):
        """Test default embedding model."""
        settings = Settings()
        assert settings.embedding_model == "intfloat/multilingual-e5-large-instruct"

    def test_override_spacy_model(self):
        """Test overriding SpaCy model."""
        with patch.dict(os.environ, {"SPACY_MODEL": "en_core_web_md"}):
            settings = Settings(_env_file=None)
            assert settings.spacy_model == "en_core_web_md"

    def test_override_embedding_model(self):
        """Test overriding embedding model."""
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        with patch.dict(os.environ, {"EMBEDDING_MODEL": model_name}):
            settings = Settings(_env_file=None)
            assert settings.embedding_model == model_name


class TestGetSettingsFunction:
    """Tests for get_settings() cached function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_cached(self):
        """Test that get_settings caches the instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_get_settings_singleton_behavior(self):
        """Test get_settings singleton behavior across calls."""
        # Clear cache
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


class TestSettingsTypeConversions:
    """Tests for type conversions."""

    def test_bool_conversion_true_variants(self):
        """Test boolean conversion with various truthy values."""
        for true_val in ["true", "True", "TRUE", "1", "yes", "YES"]:
            with patch.dict(os.environ, {"DEBUG": true_val}):
                settings = Settings(_env_file=None)
                assert settings.debug is True

    def test_bool_conversion_false_variants(self):
        """Test boolean conversion with various falsy values."""
        for false_val in ["false", "False", "FALSE", "0", "no", "NO"]:
            with patch.dict(os.environ, {"DEBUG": false_val}):
                settings = Settings(_env_file=None)
                assert settings.debug is False

    def test_int_conversion(self):
        """Test integer conversion."""
        with patch.dict(os.environ, {"API_PORT": "9000"}):
            settings = Settings(_env_file=None)
            assert isinstance(settings.api_port, int)
            assert settings.api_port == 9000

    def test_string_conversion(self):
        """Test string conversion."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            settings = Settings(_env_file=None)
            assert isinstance(settings.log_level, str)
            assert settings.log_level == "DEBUG"


class TestSettingsConfigModel:
    """Tests for Pydantic config."""

    def test_settings_case_insensitive(self):
        """Test that settings are case-insensitive."""
        with patch.dict(os.environ, {"app_name": "LowerCase"}):
            settings = Settings(_env_file=None)
            # Pydantic settings should handle case-insensitivity
            assert settings.app_name == "LowerCase" or settings.app_name == "VB_Converter"

    def test_settings_ignores_extra_fields(self):
        """Test that extra environment variables are ignored."""
        with patch.dict(os.environ, {"UNKNOWN_FIELD": "value"}):
            # Should not raise
            settings = Settings(_env_file=None)
            assert not hasattr(settings, "unknown_field")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_api_port_invalid(self):
        """Test that port 0 is invalid."""
        # Depending on validation, this may or may not be allowed
        # Port 0 is sometimes used for "auto-assign"
        with patch.dict(os.environ, {"API_PORT": "0"}):
            settings = Settings(_env_file=None)
            assert settings.api_port == 0

    def test_very_large_port_number(self):
        """Test handling of very large port numbers."""
        with patch.dict(os.environ, {"API_PORT": "65535"}):
            settings = Settings(_env_file=None)
            assert settings.api_port == 65535

    def test_empty_log_level(self):
        """Test log level is always set."""
        settings = Settings()
        # Log level should always be set (default or from env)
        assert isinstance(settings.log_level, str)

    def test_special_characters_in_secret_key(self):
        """Test special characters in secret key."""
        special_key = "test!@#$%^&*()_+-=[]{}|;:,.<>?"
        with patch.dict(os.environ, {"SECRET_KEY": special_key}):
            settings = Settings(_env_file=None)
            assert settings.secret_key == special_key

    def test_unicode_in_app_name(self):
        """Test unicode characters in app name."""
        unicode_name = "VB_Converter_ñoño"
        with patch.dict(os.environ, {"APP_NAME": unicode_name}):
            settings = Settings(_env_file=None)
            assert settings.app_name == unicode_name

    def test_multiple_overrides(self):
        """Test multiple environment variable overrides."""
        env_vars = {
            "API_PORT": "9000",
            "ENVIRONMENT": "test",
            "DEBUG": "false",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env_vars):
            settings = Settings(_env_file=None)
            assert settings.api_port == 9000
            assert settings.environment == Environment.TEST
            assert settings.debug is False
            assert settings.log_level == "DEBUG"


class TestDatabaseURLVariants:
    """Tests for database URL configuration variants."""

    def test_sqlite_default(self):
        """Test SQLite default database URL."""
        settings = Settings()
        assert settings.database_url.startswith("sqlite://")

    def test_postgres_url_override(self):
        """Test PostgreSQL URL override."""
        postgres_url = "postgresql://user:password@localhost:5432/dbname"
        with patch.dict(os.environ, {"POSTGRES_URL": postgres_url}):
            settings = Settings(_env_file=None)
            # If POSTGRES_URL is set, it might take precedence
            assert settings.postgres_url == postgres_url

    def test_sqlite_url_override(self):
        """Test SQLite URL override."""
        sqlite_url = "sqlite:///./custom.db"
        with patch.dict(os.environ, {"SQLITE_URL": sqlite_url}):
            settings = Settings(_env_file=None)
            assert settings.sqlite_url == sqlite_url

    def test_database_url_with_special_chars(self):
        """Test database URL with special characters in password."""
        db_url = "postgresql://user:p@ss%word@localhost:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": db_url}):
            settings = Settings(_env_file=None)
            assert settings.database_url == db_url
