from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.schemas.writing_profile import WritingProfileCreate
from app.services.writing_profile_service import (
    ativar_writing_profile,
    criar_writing_profile,
    listar_writing_profiles,
)

router = APIRouter(prefix="/writing-profiles", tags=["writing_profiles"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def montar_form_data(
    profile_name: str = "",
    lawyer_name: str = "",
    office_name: str = "",
    tone: str = "Formal",
    qualification_style: str = "já qualificado(a) nos autos ou a ser devidamente qualificado(a)",
    opening_phrase: str = "vem, com o devido respeito, à presença de Vossa Excelência, apresentar a presente:",
    closing_phrase: str = "Termos em que,\nPede deferimento.",
    request_intro: str = "Diante do exposto, requer:",
    legal_style_notes: str = "Utilizar linguagem jurídica formal, objetiva e técnica.",
    recurring_expressions: str = "data venia; conforme entendimento jurisprudencial; nos termos da legislação aplicável",
    is_active: bool = False,
) -> dict:
    return {
        "profile_name": profile_name,
        "lawyer_name": lawyer_name,
        "office_name": office_name,
        "tone": tone,
        "qualification_style": qualification_style,
        "opening_phrase": opening_phrase,
        "closing_phrase": closing_phrase,
        "request_intro": request_intro,
        "legal_style_notes": legal_style_notes,
        "recurring_expressions": recurring_expressions,
        "is_active": is_active,
    }


@router.get("/create", response_class=HTMLResponse)
def create_profile_form(request: Request):
    return templates.TemplateResponse(
        "writing_profile_create.html",
        {
            "request": request,
            "title": "Novo perfil de escrita",
            "error_message": None,
            "form_data": montar_form_data(),
        },
    )


@router.post("/create", response_class=HTMLResponse)
def create_profile(
    request: Request,
    profile_name: str = Form(...),
    lawyer_name: str = Form(""),
    office_name: str = Form(""),
    tone: str = Form("Formal"),
    qualification_style: str = Form(""),
    opening_phrase: str = Form(""),
    closing_phrase: str = Form(""),
    request_intro: str = Form(""),
    legal_style_notes: str = Form(""),
    recurring_expressions: str = Form(""),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    form_data = montar_form_data(
        profile_name=profile_name,
        lawyer_name=lawyer_name,
        office_name=office_name,
        tone=tone,
        qualification_style=qualification_style,
        opening_phrase=opening_phrase,
        closing_phrase=closing_phrase,
        request_intro=request_intro,
        legal_style_notes=legal_style_notes,
        recurring_expressions=recurring_expressions,
        is_active=is_active,
    )

    try:
        profile_data = WritingProfileCreate(
            profile_name=profile_name,
            lawyer_name=lawyer_name or None,
            office_name=office_name or None,
            tone=tone,
            qualification_style=qualification_style or None,
            opening_phrase=opening_phrase or None,
            closing_phrase=closing_phrase or None,
            request_intro=request_intro or None,
            legal_style_notes=legal_style_notes or None,
            recurring_expressions=recurring_expressions or None,
            is_active=is_active,
        )

        criar_writing_profile(db, profile_data)

        return RedirectResponse(url="/writing-profiles", status_code=303)

    except Exception as exc:
        return templates.TemplateResponse(
            "writing_profile_create.html",
            {
                "request": request,
                "title": "Novo perfil de escrita",
                "error_message": f"Erro ao salvar perfil: {exc}",
                "form_data": form_data,
            },
        )


@router.get("/", response_class=HTMLResponse)
def list_profiles(request: Request, db: Session = Depends(get_db)):
    perfis = listar_writing_profiles(db)

    return templates.TemplateResponse(
        "writing_profiles_list.html",
        {
            "request": request,
            "title": "Perfis de escrita",
            "perfis": perfis,
        },
    )


@router.post("/{profile_id}/activate")
def activate_profile(profile_id: int, db: Session = Depends(get_db)):
    perfil = ativar_writing_profile(db, profile_id)

    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    return RedirectResponse(url="/writing-profiles", status_code=303)