from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_NAME = os.getenv("APP_NAME", "Juridico AI")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./juridico_ai.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")

UPLOAD_PATH = BASE_DIR / UPLOAD_DIR
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)

TEMPLATES_DIR = BASE_DIR / "app" / "templates"
STATIC_DIR = BASE_DIR / "app" / "static"