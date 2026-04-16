import logging
import time
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.database import initialize_database
from app.models import Document, Generation, User, WritingProfile
from app.routers import admin, auth, documents, generations, home, plans, writing_profiles
from app.utils.logger import configure_logging

configure_logging(settings)
initialize_database()

app = FastAPI(title=settings.app_name, debug=settings.debug)
logger = logging.getLogger("app.requests")

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


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500
    extra = {
        "event": "http_request",
        "environment": settings.app_env,
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "client_host": request.client.host if request.client else None,
    }

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.exception(
            "Erro nao tratado durante requisicao HTTP.",
            extra=extra | {"status_code": status_code, "duration_ms": duration_ms},
        )
        raise
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_extra = extra | {"status_code": status_code, "duration_ms": duration_ms}
        if status_code >= 500:
            logger.error("Requisicao HTTP finalizada.", extra=log_extra)
        elif status_code >= 400:
            logger.warning("Requisicao HTTP finalizada.", extra=log_extra)
        else:
            logger.info("Requisicao HTTP finalizada.", extra=log_extra)


@app.get("/health", tags=["health"])
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
