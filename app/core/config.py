from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path (__file__).resolve().parent.parent.parent

APP_NAME = os.getenv ("APP_NAME", "Juridico AI")
DATABASE_URL = os.getenv("DATABASE?_URL", "sqlite:///./juridico_ai.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
SECRET_KEY = os.getenv("SECRET KEY", "changeme")

UPLOAD_PATH = BASE_DIR / UPLOAD_DIR
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)