from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.schemas.generation import GenerationCreate
from app.services.generation_service import (
    buscar_documentos_recentes,
    buscar_geracao_por_id,
    criar_geracao,
    gerar_minuta_inicial,
    listar_geracoes,
    montar_contexto_documentos,
    validar_dados_geracao,
)
from app.services.writing_profile_service import buscar_perfil_ativo

router = APIRouter(prefix="/generations", tags=["generations"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def montar_form_data(
    client_name: str = "",
    document_type: str = "",
    case_subject: str = "",
    facts: str = "",
    requests: str = "",
    legal_basis: str = "",
) -> dict:
    return {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
    }


@router.get("/create", response_class=HTMLResponse)
def generation_form(request: Request, db: Session = Depends(get_db)):
    perfil_ativo = buscar_perfil_ativo(db)

    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "title": "Nova geração",
            "error_message": None,
            "form_data": montar_form_data(),
            "perfil_ativo": perfil_ativo,
        },
    )


@router.post("/create", response_class=HTMLResponse)
def create_generation(
    request: Request,
    client_name: str = Form(...),
    document_type: str = Form(...),
    case_subject: str = Form(...),
    facts: str = Form(...),
    requests: str = Form(...),
    legal_basis: str = Form(""),
    db: Session = Depends(get_db),
):
    form_data = montar_form_data(
        client_name=client_name,
        document_type=document_type,
        case_subject=case_subject,
        facts=facts,
        requests=requests,
        legal_basis=legal_basis,
    )

    perfil_ativo = buscar_perfil_ativo(db)

    try:
        dados_validados = validar_dados_geracao(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis,
        )

        documentos = buscar_documentos_recentes(db, limite=3)
        contexto = montar_contexto_documentos(documentos)

        texto_gerado = gerar_minuta_inicial(
            client_name=dados_validados["client_name"],
            document_type=dados_validados["document_type"],
            case_subject=dados_validados["case_subject"],
            facts=dados_validados["facts"],
            requests=dados_validados["requests"],
            legal_basis=dados_validados["legal_basis"] or None,
            context_used=contexto,
            perfil_ativo=perfil_ativo,
        )

        generation_data = GenerationCreate(
            client_name=dados_validados["client_name"],
            document_type=dados_validados["document_type"],
            case_subject=dados_validados["case_subject"],
            facts=dados_validados["facts"],
            requests=dados_validados["requests"],
            legal_basis=dados_validados["legal_basis"] or None,
            context_used=contexto,
            generated_text=texto_gerado,
        )

        geracao = criar_geracao(db, generation_data)

        return templates.TemplateResponse(
            "generation_result.html",
            {
                "request": request,
                "title": "Resultado da geração",
                "geracao": geracao,
                "perfil_ativo": perfil_ativo,
            },
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "generate.html",
            {
                "request": request,
                "title": "Nova geração",
                "error_message": str(exc),
                "form_data": form_data,
                "perfil_ativo": perfil_ativo,
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "generate.html",
            {
                "request": request,
                "title": "Nova geração",
                "error_message": f"Ocorreu um erro ao gerar a minuta: {exc}",
                "form_data": form_data,
                "perfil_ativo": perfil_ativo,
            },
        )


@router.get("/", response_class=HTMLResponse)
def generations_list(request: Request, db: Session = Depends(get_db)):
    geracoes = listar_geracoes(db)

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "title": "Gerações salvas",
            "geracoes": geracoes,
        },
    )


@router.get("/{generation_id}", response_class=HTMLResponse)
def generation_detail(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    perfil_ativo = buscar_perfil_ativo(db)

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao,
            "perfil_ativo": perfil_ativo,
        },
    )