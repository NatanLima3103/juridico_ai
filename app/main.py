from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.database import initialize_database
from app.models import Document, Generation, User, WritingProfile
from app.routers import admin, auth, documents, generations, home, plans, writing_profiles

initialize_database()

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    https_only=settings.session_cookie_secure,
)

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(home.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(generations.router)
app.include_router(writing_profiles.router)
app.include_router(plans.router)


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
