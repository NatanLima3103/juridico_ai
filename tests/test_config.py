from pathlib import Path

import pytest

from app.core.config import AppSettings


def test_settings_carrega_defaults_centralizados():
    settings = AppSettings.from_env({}, base_dir=Path("/app"))

    assert settings.app_name == "Juridico AI"
    assert settings.app_env == "development"
    assert settings.debug is True
    assert settings.database_url == "sqlite:///./juridico_ai.db"
    assert settings.upload_path == Path("/app/storage/uploads")
    assert settings.generations_path == Path("/app/storage/generations")
    assert settings.max_upload_size_bytes == 10 * 1024 * 1024


def test_settings_respeita_env_e_fallback_legado():
    settings = AppSettings.from_env(
        {
            "APP_ENV": "production",
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
    assert settings.is_production is True
    assert settings.debug is False
    assert settings.session_cookie_secure is True
    assert settings.free_plan_daily_generation_limit == 7
    assert settings.upload_path == Path("/var/lib/juridico/uploads")


def test_settings_bloqueia_secret_key_padrao_em_producao():
    settings = AppSettings.from_env({"APP_ENV": "production"}, base_dir=Path("/app"))

    with pytest.raises(ValueError, match="SECRET_KEY"):
        settings.validate()
