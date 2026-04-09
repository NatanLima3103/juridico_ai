from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import APP_NAME, SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import initialize_database
from app.models import Document, Generation, User, WritingProfile
from app.routers import auth, documents, generations, home, writing_profiles

initialize_database()

app = FastAPI(title=APP_NAME)

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(home.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(generations.router)
app.include_router(writing_profiles.router)
