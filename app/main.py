from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import STATIC_DIR
from app.database import Base, engine
from app.models import Document, Generation, WritingProfile
from app.routers import documents, generations, writing_profiles

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Juridico AI")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(documents.router)
app.include_router(generations.router)
app.include_router(writing_profiles.router)