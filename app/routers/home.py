from collections import Counter

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_authenticated_user
from app.models.document import Document
from app.models.generation import Generation
from app.models.user import User
from app.models.writing_profile import WritingProfile
from app.routers.common import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    total_documents = db.query(Document).filter(Document.user_id == usuario.id, Document.deleted_at.is_(None)).count()
    total_profiles = db.query(WritingProfile).filter(WritingProfile.user_id == usuario.id, WritingProfile.deleted_at.is_(None)).count()
    total_generations = db.query(Generation).filter(Generation.user_id == usuario.id, Generation.deleted_at.is_(None)).count()

    recent_documents = (
        db.query(Document)
        .filter(Document.user_id == usuario.id, Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(4)
        .all()
    )

    recent_profiles = (
        db.query(WritingProfile)
        .filter(WritingProfile.user_id == usuario.id, WritingProfile.deleted_at.is_(None))
        .order_by(WritingProfile.is_pinned.desc(), WritingProfile.created_at.desc(), WritingProfile.id.desc())
        .limit(4)
        .all()
    )

    recent_generations = (
        db.query(Generation)
        .filter(Generation.user_id == usuario.id, Generation.deleted_at.is_(None))
        .order_by(Generation.is_pinned.desc(), Generation.updated_at.desc(), Generation.id.desc())
        .limit(5)
        .all()
    )

    generation_types = []
    for generation in db.query(Generation).filter(Generation.user_id == usuario.id, Generation.deleted_at.is_(None)).all():
        tipo = (generation.document_type or "Não informado").strip()
        generation_types.append(tipo or "Não informado")

    generation_type_summary = [
        {"label": label, "count": count}
        for label, count in Counter(generation_types).most_common(5)
    ]

    latest_generation = recent_generations[0] if recent_generations else None
    latest_document = recent_documents[0] if recent_documents else None
    latest_profile = recent_profiles[0] if recent_profiles else None

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Página inicial",
            "total_documents": total_documents,
            "total_profiles": total_profiles,
            "total_generations": total_generations,
            "recent_documents": recent_documents,
            "recent_profiles": recent_profiles,
            "recent_generations": recent_generations,
            "generation_type_summary": generation_type_summary,
            "latest_generation": latest_generation,
            "latest_document": latest_document,
            "latest_profile": latest_profile,
        },
    )
