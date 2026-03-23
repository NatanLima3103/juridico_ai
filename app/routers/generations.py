from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.schemas.generation import GenerationCreate
from app.services.document_service import listar_documentos, listar_documentos_por_ids
from app.services.generation_service import (
    buscar_geracao_por_id,
    contar_caracteres_texto_gerado,
    contar_documentos_no_contexto,
    criar_geracao,
    extrair_ids_do_contexto,
    gerar_minuta_inicial,
    listar_geracoes,
    montar_contexto_documentos,
    resumir_contexto,
    resumir_texto_gerado,
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
    documentos = listar_documentos(db)

    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "title": "Nova geração",
            "error_message": None,
            "form_data": montar_form_data(),
            "perfil_ativo": perfil_ativo,
            "documentos": documentos,
            "selected_document_ids": [],
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
    selected_document_ids: list[int] = Form(default=[]),
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
    documentos = listar_documentos(db)

    try:
        dados_validados = validar_dados_geracao(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis,
        )

        documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)
        contexto = montar_contexto_documentos(documentos_selecionados)

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
                "documentos_utilizados": documentos_selecionados,
                "total_documentos_utilizados": len(documentos_selecionados),
                "texto_gerado_preview": resumir_texto_gerado(geracao.generated_text, 350),
                "total_caracteres_gerados": contar_caracteres_texto_gerado(
                    geracao.generated_text
                ),
                "contexto_preview": resumir_contexto(geracao.context_used, 350),
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
                "documentos": documentos,
                "selected_document_ids": selected_document_ids,
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
                "documentos": documentos,
                "selected_document_ids": selected_document_ids,
            },
        )


@router.get("/", response_class=HTMLResponse)
def generations_list(request: Request, db: Session = Depends(get_db)):
    geracoes = listar_geracoes(db)

    geracoes_view = []
    for geracao in geracoes:
        geracoes_view.append(
            {
                "id": geracao.id,
                "client_name": geracao.client_name,
                "document_type": geracao.document_type,
                "case_subject": geracao.case_subject,
                "created_at": geracao.created_at,
                "generated_text_preview": resumir_texto_gerado(
                    geracao.generated_text, 180
                ),
                "generated_text_length": contar_caracteres_texto_gerado(
                    geracao.generated_text
                ),
                "documents_count": contar_documentos_no_contexto(geracao.context_used),
            }
        )

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "title": "Gerações salvas",
            "geracoes": geracoes_view,
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
    ids_documentos = extrair_ids_do_contexto(geracao.context_used)
    documentos_utilizados = listar_documentos_por_ids(db, ids_documentos)

    geracao_view = {
        "id": geracao.id,
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis,
        "context_used": geracao.context_used,
        "generated_text": geracao.generated_text,
        "created_at": geracao.created_at,
        "generated_text_length": contar_caracteres_texto_gerado(geracao.generated_text),
        "context_preview": resumir_contexto(geracao.context_used, 300),
        "documents_count": len(documentos_utilizados),
    }

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao_view,
            "perfil_ativo": perfil_ativo,
            "documentos_utilizados": documentos_utilizados,
        },
    )