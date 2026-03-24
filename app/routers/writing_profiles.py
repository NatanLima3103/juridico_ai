from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.schemas.writing_profile import WritingProfileCreate
from app.services.writing_profile_service import (
    ativar_perfil,
    buscar_perfil_ativo,
    buscar_perfil_por_id,
    criar_perfil,
    listar_perfis,
    montar_resumo_perfil,
    validar_dados_perfil,
)

router = APIRouter(prefix="/writing-profiles", tags=["writing_profiles"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def montar_form_data(
    profile_name: str = "",
    tone: str = "",
    lawyer_name: str = "",
    office_name: str = "",
    qualification_style: str = "",
    opening_phrase: str = "",
    request_intro: str = "",
    closing_phrase: str = "",
    legal_style_notes: str = "",
    recurring_expressions: str = "",
) -> dict:
    return {
        "profile_name": profile_name,
        "tone": tone,
        "lawyer_name": lawyer_name,
        "office_name": office_name,
        "qualification_style": qualification_style,
        "opening_phrase": opening_phrase,
        "request_intro": request_intro,
        "closing_phrase": closing_phrase,
        "legal_style_notes": legal_style_notes,
        "recurring_expressions": recurring_expressions,
    }


@router.get("/", response_class=HTMLResponse)
def profiles_list(request: Request, db: Session = Depends(get_db)):
    perfis = listar_perfis(db)
    perfis_view = [montar_resumo_perfil(perfil) for perfil in perfis]
    perfil_ativo = buscar_perfil_ativo(db)

    return templates.TemplateResponse(
        "writing_profiles_list.html",
        {
            "request": request,
            "title": "Perfis de escrita",
            "perfis": perfis_view,
            "perfil_ativo": perfil_ativo,
        },
    )


@router.get("/create", response_class=HTMLResponse)
def create_profile_page(request: Request):
    return templates.TemplateResponse(
        "writing_profile_form.html",
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
    tone: str = Form(...),
    lawyer_name: str = Form(""),
    office_name: str = Form(""),
    qualification_style: str = Form(""),
    opening_phrase: str = Form(""),
    request_intro: str = Form(""),
    closing_phrase: str = Form(""),
    legal_style_notes: str = Form(""),
    recurring_expressions: str = Form(""),
    db: Session = Depends(get_db),
):
    form_data = montar_form_data(
        profile_name=profile_name,
        tone=tone,
        lawyer_name=lawyer_name,
        office_name=office_name,
        qualification_style=qualification_style,
        opening_phrase=opening_phrase,
        request_intro=request_intro,
        closing_phrase=closing_phrase,
        legal_style_notes=legal_style_notes,
        recurring_expressions=recurring_expressions,
    )

    try:
        dados = validar_dados_perfil(
            profile_name=profile_name,
            tone=tone,
            lawyer_name=lawyer_name,
            office_name=office_name,
            qualification_style=qualification_style,
            opening_phrase=opening_phrase,
            request_intro=request_intro,
            closing_phrase=closing_phrase,
            legal_style_notes=legal_style_notes,
            recurring_expressions=recurring_expressions,
        )

        profile_data = WritingProfileCreate(
            profile_name=dados["profile_name"],
            tone=dados["tone"],
            lawyer_name=dados["lawyer_name"],
            office_name=dados["office_name"],
            qualification_style=dados["qualification_style"],
            opening_phrase=dados["opening_phrase"],
            request_intro=dados["request_intro"],
            closing_phrase=dados["closing_phrase"],
            legal_style_notes=dados["legal_style_notes"],
            recurring_expressions=dados["recurring_expressions"],
        )

        criar_perfil(db, profile_data)

        return RedirectResponse(
            url="/writing-profiles",
            status_code=303,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "writing_profile_form.html",
            {
                "request": request,
                "title": "Novo perfil de escrita",
                "error_message": str(exc),
                "form_data": form_data,
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "writing_profile_form.html",
            {
                "request": request,
                "title": "Novo perfil de escrita",
                "error_message": f"Ocorreu um erro ao criar o perfil: {exc}",
                "form_data": form_data,
            },
        )


@router.post("/{profile_id}/activate")
def activate_profile(profile_id: int, db: Session = Depends(get_db)):
    perfil = buscar_perfil_por_id(db, profile_id)

    if not perfil:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")

    ativar_perfil(db, profile_id)

    return RedirectResponse(
        url="/writing-profiles",
        status_code=303,
    )