from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.writing_profile import WritingProfileCreate
from app.services.generation_service import resumir_texto
from app.services.writing_profile_service import (
    ativar_perfil,
    buscar_perfil_ativo,
    criar_perfil,
    excluir_perfil,
    listar_perfis,
    montar_resumo_perfil,
    validar_dados_perfil,
)

router = APIRouter(prefix="/writing-profiles", tags=["Perfis de escrita"])
templates = Jinja2Templates(directory="app/templates")


@router.get("")
def listar_perfis_page(request: Request, db: Session = Depends(get_db)):
    perfis = listar_perfis(db)
    perfil_ativo = buscar_perfil_ativo(db)

    perfis_resumo = []
    for perfil in perfis:
        resumo = montar_resumo_perfil(perfil)
        resumo["qualification_style_preview"] = resumir_texto(resumo["qualification_style"], 80)
        resumo["opening_phrase_preview"] = resumir_texto(resumo["opening_phrase"], 80)
        resumo["request_intro_preview"] = resumir_texto(resumo["request_intro"], 80)
        resumo["closing_phrase_preview"] = resumir_texto(resumo["closing_phrase"], 80)
        resumo["legal_style_notes_preview"] = resumir_texto(resumo["legal_style_notes"], 100)
        resumo["recurring_expressions_preview"] = resumir_texto(resumo["recurring_expressions"], 100)
        perfis_resumo.append(resumo)

    return templates.TemplateResponse(
        "writing_profiles_list.html",
        {
            "request": request,
            "perfis": perfis_resumo,
            "perfil_ativo": perfil_ativo,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("/create")
def exibir_formulario_perfil(request: Request):
    return templates.TemplateResponse(
        "writing_profile_form.html",
        {
            "request": request,
            "erro": None,
            "form_data": {},
        },
    )


@router.post("/create")
def criar_perfil_page(
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

        payload = WritingProfileCreate(**dados)
        criar_perfil(db, payload)

        return RedirectResponse(
            url="/writing-profiles?sucesso=Perfil criado com sucesso.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except ValueError as exc:
        return templates.TemplateResponse(
            "writing_profile_form.html",
            {
                "request": request,
                "erro": str(exc),
                "form_data": {
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
                },
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.post("/{profile_id}/activate")
def ativar_perfil_page(profile_id: int, db: Session = Depends(get_db)):
    perfil = ativar_perfil(db, profile_id)

    if not perfil:
        return RedirectResponse(
            url="/writing-profiles?erro=Perfil não encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url="/writing-profiles?sucesso=Perfil ativado com sucesso.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{profile_id}/delete")
def excluir_perfil_page(profile_id: int, db: Session = Depends(get_db)):
    sucesso, mensagem = excluir_perfil(db, profile_id)

    if not sucesso:
        return RedirectResponse(
            url=f"/writing-profiles?erro={mensagem}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/writing-profiles?sucesso={mensagem}",
        status_code=status.HTTP_303_SEE_OTHER,
    )