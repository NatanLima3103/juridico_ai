from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME, STATIC_DIR
from app.database import Base, engine
from app.models import Document, Generation, WritingProfile
from app.routers import documents, generations, home, writing_profiles

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_NAME)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(home.router)
app.include_router(documents.router)
app.include_router(generations.router)
app.include_router(writing_profiles.router)