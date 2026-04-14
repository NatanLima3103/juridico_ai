from pathlib import Path

import pytest

from app.core.config import AppSettings


def test_settings_carrega_defaults_centralizados():
    settings = AppSettings.from_env({}, base_dir=Path("/app"))

    assert settings.app_name == "Juridico AI"
    assert settings.app_env == "development"
    assert settings.env_file == ".env"
    assert settings.debug is True
    assert settings.database_url == "sqlite:///./juridico_ai.db"
    assert settings.upload_path == Path("/app/storage/uploads")
    assert settings.generations_path == Path("/app/storage/generations")
    assert settings.max_upload_size_bytes == 10 * 1024 * 1024


def test_settings_respeita_env_e_fallback_legado():
    settings = AppSettings.from_env(
        {
            "APP_ENV": "production",
            "ENV_FILE": ".env.production",
            "APP_NAME": "Juridico AI Producao",
            "DATABASE_URL": "postgresql+psycopg://user:pass@db:5432/juridico",
            "SECRET_KEY": "uma-chave-real",
            "UPLOAD_DIR": "/var/lib/juridico/uploads",
            "FREE_PLAN_MONTHLY_GENERATION_LIMIT": "7",
            "SESSION_COOKIE_SECURE": "true",
        },
        base_dir=Path("/app"),
    )

    assert settings.app_name == "Juridico AI Producao"
    assert settings.env_file == ".env.production"
    assert settings.is_production is True
    assert settings.debug is False
    assert settings.session_cookie_secure is True
    assert settings.free_plan_daily_generation_limit == 7
    assert settings.upload_path == Path("/var/lib/juridico/uploads")


def test_settings_bloqueia_secret_key_padrao_em_producao():
    settings = AppSettings.from_env({"APP_ENV": "production"}, base_dir=Path("/app"))

    with pytest.raises(ValueError, match="SECRET_KEY"):
        settings.validate()


def test_settings_bloqueia_variaveis_inseguras_em_producao():
    settings = AppSettings.from_env(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "troque-esta-chave-em-producao",
            "DATABASE_URL": "sqlite:///./juridico_ai.db",
            "SESSION_COOKIE_SECURE": "false",
        },
        base_dir=Path("/app"),
    )

    with pytest.raises(ValueError) as exc_info:
        settings.validate()

    message = str(exc_info.value)
    assert "SECRET_KEY" in message
    assert "DATABASE_URL" in message
    assert "SESSION_COOKIE_SECURE" in message


def test_settings_valida_limites_numericos():
    settings = AppSettings.from_env(
        {
            "RAG_CHUNK_SIZE": "0",
            "OPENAI_MAX_OUTPUT_TOKENS": "0",
            "PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS": "0",
            "FREE_PLAN_DAILY_GENERATION_LIMIT": "-1",
        },
        base_dir=Path("/app"),
    )

    with pytest.raises(ValueError) as exc_info:
        settings.validate()

    message = str(exc_info.value)
    assert "RAG_CHUNK_SIZE" in message
    assert "OPENAI_MAX_OUTPUT_TOKENS" in message
    assert "PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS" in message
    assert "FREE_PLAN_DAILY_GENERATION_LIMIT" in message
