from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_authenticated_user
from app.models.user import User
from app.routers.common import templates
from app.services.plan_service import listar_planos_disponiveis, obter_uso_plano_usuario

router = APIRouter(
    prefix="/plans",
    tags=["plans"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.get("", response_class=HTMLResponse)
def plans_page(
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    plan_usage = obter_uso_plano_usuario(db, usuario)

    return templates.TemplateResponse(
        "plans.html",
        {
            "request": request,
            "title": "Planos",
            "plan_usage": plan_usage,
            "planos": listar_planos_disponiveis(),
        },
    )
