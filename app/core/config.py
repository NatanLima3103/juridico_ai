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
