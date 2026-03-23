from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.services.document_service import listar_documentos, listar_documentos_por_ids
from app.services.generation_service import (
    TIPOS_DE_DOCUMENTO,
    buscar_geracao_por_id,
    criar_geracao,
    gerar_rascunho_juridico,
    listar_geracoes,
    montar_contexto_documental,
    resumir_texto,
)

router = APIRouter(prefix="/generations", tags=["generations"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
                "facts_preview": resumir_texto(geracao.facts, 180),
                "requests_preview": resumir_texto(geracao.requests, 180),
                "generated_text_preview": resumir_texto(geracao.generated_text, 220),
                "created_at": geracao.created_at,
            }
        )

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "title": "Histórico de gerações",
            "geracoes": geracoes_view,
        },
    )


@router.get("/create", response_class=HTMLResponse)
def create_generation_page(request: Request, db: Session = Depends(get_db)):
    documentos = listar_documentos(db)

    return templates.TemplateResponse(
        "generation_create.html",
        {
            "request": request,
            "title": "Nova geração jurídica",
            "documentos": documentos,
            "tipos_de_documento": TIPOS_DE_DOCUMENTO,
            "error_message": None,
            "form_data": {},
            "selected_document_ids": [],
        },
    )


@router.post("/create", response_class=HTMLResponse)
async def create_generation(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    client_name = str(form.get("client_name", "")).strip()
    document_type = str(form.get("document_type", "")).strip()
    case_subject = str(form.get("case_subject", "")).strip()
    facts = str(form.get("facts", "")).strip()
    requests = str(form.get("requests", "")).strip()
    legal_basis = str(form.get("legal_basis", "")).strip()

    raw_document_ids = form.getlist("document_ids")
    selected_document_ids = []

    for item in raw_document_ids:
        item_str = str(item).strip()
        if item_str.isdigit():
            selected_document_ids.append(int(item_str))

    documentos = listar_documentos(db)

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
    }

    if not client_name or not document_type or not case_subject or not facts or not requests:
        return templates.TemplateResponse(
            "generation_create.html",
            {
                "request": request,
                "title": "Nova geração jurídica",
                "documentos": documentos,
                "tipos_de_documento": TIPOS_DE_DOCUMENTO,
                "error_message": "Preencha cliente, tipo de documento, assunto, fatos e pedidos.",
                "form_data": form_data,
                "selected_document_ids": selected_document_ids,
            },
        )

    documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)

    if not documentos_selecionados:
        return templates.TemplateResponse(
            "generation_create.html",
            {
                "request": request,
                "title": "Nova geração jurídica",
                "documentos": documentos,
                "tipos_de_documento": TIPOS_DE_DOCUMENTO,
                "error_message": "Selecione pelo menos um documento base.",
                "form_data": form_data,
                "selected_document_ids": selected_document_ids,
            },
        )

    context_used = montar_contexto_documental(documentos_selecionados)

    generated_text = gerar_rascunho_juridico(
        client_name=client_name,
        document_type=document_type,
        case_subject=case_subject,
        facts=facts,
        requests=requests,
        legal_basis=legal_basis,
        context_used=context_used,
    )

    geracao = criar_geracao(
        db=db,
        client_name=client_name,
        document_type=document_type,
        case_subject=case_subject,
        facts=facts,
        requests=requests,
        legal_basis=legal_basis,
        context_used=context_used,
        generated_text=generated_text,
    )

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao,
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

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao,
        },
    )