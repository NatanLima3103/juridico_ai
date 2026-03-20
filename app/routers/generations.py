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
)

router = APIRouter(prefix="/generations", tags=["generations"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/create", response_class=HTMLResponse)
def generation_form(request: Request):
    return templates.TemplateResponse(
        "generate.html",
        {
            "request": request,
            "title": "Nova geração",
            "error_message": None,
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
    try:
        documentos = buscar_documentos_recentes(db, limite=3)
        contexto = montar_contexto_documentos(documentos)

        texto_gerado = gerar_minuta_inicial(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis if legal_basis.strip() else None,
            context_used=contexto,
        )

        generation_data = GenerationCreate(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis if legal_basis.strip() else None,
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
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "generate.html",
            {
                "request": request,
                "title": "Nova geração",
                "error_message": f"Ocorreu um erro ao gerar a minuta: {exc}",
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

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao,
        },
    )