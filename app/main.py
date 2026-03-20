from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_NAME, STATIC_DIR
from app.database import Base, engine
import app.models
from app.routers import documents, generations, home

Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_NAME)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(home.router)
app.include_router(documents.router)
app.include_router(generations.router)