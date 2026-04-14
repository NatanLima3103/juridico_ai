import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _str(env: Mapping[str, str], name: str, default: str = "") -> str:
    return str(env.get(name, default)).strip()


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw_value = _str(env, name, str(default))
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um numero inteiro.") from exc


def _bool(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw_value = _str(env, name, str(default)).lower()
    return raw_value in {"1", "true", "t", "yes", "y", "sim", "s", "on"}


def _path_from_base(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_name: str
    app_env: str
    env_file: str
    debug: bool
    base_dir: Path
    database_url: str
    secret_key: str
    session_cookie_name: str
    session_cookie_secure: bool
    password_reset_token_max_age_seconds: int
    openai_api_key: str
    openai_model: str
    openai_reasoning_effort: str
    openai_max_output_tokens: int
    openai_embedding_model: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_top_k: int
    rag_vector_dimension: int
    free_plan_daily_generation_limit: int
    pro_plan_monthly_generation_limit: int
    free_plan_writing_profile_limit: int
    pro_plan_writing_profile_limit: int
    payment_provider: str
    payment_checkout_url: str
    payment_success_url: str
    payment_cancel_url: str
    payment_webhook_secret: str
    soft_deleted_retention_days: int
    audit_log_retention_days: int
    upload_dir: str
    generations_dir: str
    max_upload_size_mb: int
    templates_dir: Path
    static_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, *, base_dir: Path = BASE_DIR) -> "AppSettings":
        env = os.environ if env is None else env
        app_env = _str(env, "APP_ENV", _str(env, "ENVIRONMENT", "development")).lower() or "development"
        free_daily_default = _int(env, "FREE_PLAN_MONTHLY_GENERATION_LIMIT", 10)

        return cls(
            app_name=_str(env, "APP_NAME", "Juridico AI") or "Juridico AI",
            app_env=app_env,
            env_file=_str(env, "ENV_FILE", ".env") or ".env",
            debug=_bool(env, "DEBUG", app_env != "production"),
            base_dir=base_dir,
            database_url=_str(env, "DATABASE_URL", "sqlite:///./juridico_ai.db") or "sqlite:///./juridico_ai.db",
            secret_key=_str(env, "SECRET_KEY", "changeme") or "changeme",
            session_cookie_name=_str(env, "SESSION_COOKIE_NAME", "session") or "session",
            session_cookie_secure=_bool(env, "SESSION_COOKIE_SECURE", app_env == "production"),
            password_reset_token_max_age_seconds=_int(env, "PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", 3600),
            openai_api_key=_str(env, "OPENAI_API_KEY"),
            openai_model=_str(env, "OPENAI_MODEL", "gpt-5-mini") or "gpt-5-mini",
            openai_reasoning_effort=_str(env, "OPENAI_REASONING_EFFORT"),
            openai_max_output_tokens=_int(env, "OPENAI_MAX_OUTPUT_TOKENS", 2200),
            openai_embedding_model=_str(env, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            or "text-embedding-3-small",
            rag_chunk_size=_int(env, "RAG_CHUNK_SIZE", 800),
            rag_chunk_overlap=_int(env, "RAG_CHUNK_OVERLAP", 120),
            rag_top_k=_int(env, "RAG_TOP_K", 4),
            rag_vector_dimension=_int(env, "RAG_VECTOR_DIMENSION", 128),
            free_plan_daily_generation_limit=_int(env, "FREE_PLAN_DAILY_GENERATION_LIMIT", free_daily_default),
            pro_plan_monthly_generation_limit=_int(env, "PRO_PLAN_MONTHLY_GENERATION_LIMIT", 1000),
            free_plan_writing_profile_limit=_int(env, "FREE_PLAN_WRITING_PROFILE_LIMIT", 5),
            pro_plan_writing_profile_limit=_int(env, "PRO_PLAN_WRITING_PROFILE_LIMIT", 25),
            payment_provider=_str(env, "PAYMENT_PROVIDER", "manual").lower() or "manual",
            payment_checkout_url=_str(env, "PAYMENT_CHECKOUT_URL"),
            payment_success_url=_str(env, "PAYMENT_SUCCESS_URL"),
            payment_cancel_url=_str(env, "PAYMENT_CANCEL_URL"),
            payment_webhook_secret=_str(env, "PAYMENT_WEBHOOK_SECRET"),
            soft_deleted_retention_days=_int(env, "SOFT_DELETED_RETENTION_DAYS", 30),
            audit_log_retention_days=_int(env, "AUDIT_LOG_RETENTION_DAYS", 180),
            upload_dir=_str(env, "UPLOAD_DIR", "storage/uploads") or "storage/uploads",
            generations_dir=_str(env, "GENERATIONS_DIR", "storage/generations") or "storage/generations",
            max_upload_size_mb=_int(env, "MAX_UPLOAD_SIZE_MB", 10),
            templates_dir=base_dir / "app" / "templates",
            static_dir=base_dir / "app" / "static",
        )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return _path_from_base(self.base_dir, self.upload_dir)

    @property
    def generations_path(self) -> Path:
        return _path_from_base(self.base_dir, self.generations_dir)

    def ensure_storage_dirs(self) -> None:
        self.upload_path.mkdir(parents=True, exist_ok=True)
        self.generations_path.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        errors: list[str] = []

        if self.rag_chunk_size <= 0:
            errors.append("RAG_CHUNK_SIZE deve ser maior que zero.")
        if self.rag_chunk_overlap < 0:
            errors.append("RAG_CHUNK_OVERLAP nao pode ser negativo.")
        if self.rag_top_k <= 0:
            errors.append("RAG_TOP_K deve ser maior que zero.")
        if self.rag_vector_dimension <= 0:
            errors.append("RAG_VECTOR_DIMENSION deve ser maior que zero.")
        if self.max_upload_size_mb <= 0:
            errors.append("MAX_UPLOAD_SIZE_MB deve ser maior que zero.")
        if self.soft_deleted_retention_days <= 0:
            errors.append("SOFT_DELETED_RETENTION_DAYS deve ser maior que zero.")
        if self.audit_log_retention_days <= 0:
            errors.append("AUDIT_LOG_RETENTION_DAYS deve ser maior que zero.")
        if self.password_reset_token_max_age_seconds <= 0:
            errors.append("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS deve ser maior que zero.")
        if self.openai_max_output_tokens <= 0:
            errors.append("OPENAI_MAX_OUTPUT_TOKENS deve ser maior que zero.")
        if self.free_plan_daily_generation_limit < 0:
            errors.append("FREE_PLAN_DAILY_GENERATION_LIMIT nao pode ser negativo.")
        if self.pro_plan_monthly_generation_limit < 0:
            errors.append("PRO_PLAN_MONTHLY_GENERATION_LIMIT nao pode ser negativo.")
        if self.free_plan_writing_profile_limit < 0:
            errors.append("FREE_PLAN_WRITING_PROFILE_LIMIT nao pode ser negativo.")
        if self.pro_plan_writing_profile_limit < 0:
            errors.append("PRO_PLAN_WRITING_PROFILE_LIMIT nao pode ser negativo.")

        if self.is_production:
            secret_key_insegura = {"", "changeme", "troque-esta-chave-em-producao"}
            if self.secret_key in secret_key_insegura:
                errors.append("SECRET_KEY deve ser configurada fora do valor padrao em producao.")
            if self.database_url == "sqlite:///./juridico_ai.db":
                errors.append("DATABASE_URL deve apontar para o banco de producao.")
            if not self.session_cookie_secure:
                errors.append("SESSION_COOKIE_SECURE deve ser true em producao.")

        if errors:
            raise ValueError(" ".join(errors))


def load_settings() -> AppSettings:
    env_file = os.environ.get("ENV_FILE")
    if env_file:
        load_dotenv(dotenv_path=env_file)
    else:
        load_dotenv()
    settings = AppSettings.from_env()
    settings.validate()
    settings.ensure_storage_dirs()
    return settings


settings = load_settings()

APP_NAME = settings.app_name
APP_ENV = settings.app_env
ENV_FILE = settings.env_file
DEBUG = settings.debug
DATABASE_URL = settings.database_url
SECRET_KEY = settings.secret_key
SESSION_COOKIE_NAME = settings.session_cookie_name
SESSION_COOKIE_SECURE = settings.session_cookie_secure
PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = settings.password_reset_token_max_age_seconds
OPENAI_API_KEY = settings.openai_api_key
OPENAI_MODEL = settings.openai_model
OPENAI_REASONING_EFFORT = settings.openai_reasoning_effort
OPENAI_MAX_OUTPUT_TOKENS = settings.openai_max_output_tokens
OPENAI_EMBEDDING_MODEL = settings.openai_embedding_model
RAG_CHUNK_SIZE = settings.rag_chunk_size
RAG_CHUNK_OVERLAP = settings.rag_chunk_overlap
RAG_TOP_K = settings.rag_top_k
RAG_VECTOR_DIMENSION = settings.rag_vector_dimension
FREE_PLAN_DAILY_GENERATION_LIMIT = settings.free_plan_daily_generation_limit
PRO_PLAN_MONTHLY_GENERATION_LIMIT = settings.pro_plan_monthly_generation_limit
FREE_PLAN_WRITING_PROFILE_LIMIT = settings.free_plan_writing_profile_limit
PRO_PLAN_WRITING_PROFILE_LIMIT = settings.pro_plan_writing_profile_limit
PAYMENT_PROVIDER = settings.payment_provider
PAYMENT_CHECKOUT_URL = settings.payment_checkout_url
PAYMENT_SUCCESS_URL = settings.payment_success_url
PAYMENT_CANCEL_URL = settings.payment_cancel_url
PAYMENT_WEBHOOK_SECRET = settings.payment_webhook_secret
SOFT_DELETED_RETENTION_DAYS = settings.soft_deleted_retention_days
AUDIT_LOG_RETENTION_DAYS = settings.audit_log_retention_days
UPLOAD_DIR = settings.upload_dir
GENERATIONS_DIR = settings.generations_dir
MAX_UPLOAD_SIZE_MB = settings.max_upload_size_mb
MAX_UPLOAD_SIZE_BYTES = settings.max_upload_size_bytes
UPLOAD_PATH = settings.upload_path
GENERATIONS_PATH = settings.generations_path
TEMPLATES_DIR = settings.templates_dir
STATIC_DIR = settings.static_dir
