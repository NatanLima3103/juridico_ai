from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_NAME = os.getenv("APP_NAME", "Juridico AI")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./juridico_ai.db")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session")
PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS = int(os.getenv("PASSWORD_RESET_TOKEN_MAX_AGE_SECONDS", "3600"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "").strip()
OPENAI_MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2200"))
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small").strip() or "text-embedding-3-small"

RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_VECTOR_DIMENSION = int(os.getenv("RAG_VECTOR_DIMENSION", "128"))
FREE_PLAN_MONTHLY_GENERATION_LIMIT = int(os.getenv("FREE_PLAN_MONTHLY_GENERATION_LIMIT", "5"))
PRO_PLAN_MONTHLY_GENERATION_LIMIT = int(os.getenv("PRO_PLAN_MONTHLY_GENERATION_LIMIT", "100"))
FREE_PLAN_WRITING_PROFILE_LIMIT = int(os.getenv("FREE_PLAN_WRITING_PROFILE_LIMIT", "1"))
PRO_PLAN_WRITING_PROFILE_LIMIT = int(os.getenv("PRO_PLAN_WRITING_PROFILE_LIMIT", "10"))

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "storage/uploads")
GENERATIONS_DIR = os.getenv("GENERATIONS_DIR", "storage/generations")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

UPLOAD_PATH = BASE_DIR / UPLOAD_DIR
GENERATIONS_PATH = BASE_DIR / GENERATIONS_DIR

UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
GENERATIONS_PATH.mkdir(parents=True, exist_ok=True)

TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"
