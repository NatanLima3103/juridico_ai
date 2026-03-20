from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import TEMPLATES_DIR
from app.database import get_db
from app.services.document_service import (
    buscar_documento_por_id,
    criar_documento,
    listar_documentos,
    montar_dados_documento,
)
from app.services.file_service import salvar_arquivo_upload
from app.services.text_extractor import extrair_texto_arquivo

router = APIRouter(prefix="/documents", tags=["documents"])
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "title": "Upload de documentos",
            "error_message": None,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        saved_path = await salvar_arquivo_upload(file)
        extracted_text = extrair_texto_arquivo(saved_path)

        document_data = montar_dados_documento(
            original_filename=file.filename,
            saved_path=saved_path,
            extracted_text=extracted_text,
        )
        documento = criar_documento(db, document_data)

        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "title": "Resultado do documento",
                "filename": documento.original_filename,
                "file_path": documento.file_path,
                "extracted_text": documento.extracted_text,
                "document_id": documento.id,
            },
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "Upload de documentos",
                "error_message": str(exc),
            },
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "Upload de documentos",
                "error_message": f"Ocorreu um erro ao processar o arquivo: {exc}",
            },
        )


@router.get("/", response_class=HTMLResponse)
def documents_list(request: Request, db: Session = Depends(get_db)):
    documentos = listar_documentos(db)

    return templates.TemplateResponse(
        "documents_list.html",
        {
            "request": request,
            "title": "Documentos enviados",
            "documentos": documentos,
        },
    )


@router.get("/{document_id}", response_class=HTMLResponse)
def document_detail(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    documento = buscar_documento_por_id(db, document_id)

    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    return templates.TemplateResponse(
        "document_detail.html",
        {
            "request": request,
            "title": "Detalhes do documento",
            "documento": documento,
        },
    )