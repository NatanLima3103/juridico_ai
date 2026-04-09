from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import MAX_UPLOAD_SIZE_MB
from app.database import get_db
from app.dependencies.auth import get_authenticated_user
from app.routers.common import templates
from app.services.document_service import (
    ORDENACOES_DOCUMENTOS,
    buscar_documento_por_id,
    contar_caracteres_texto,
    contar_palavras_texto,
    criar_documento,
    documento_existe,
    excluir_documento,
    formatar_tamanho_arquivo,
    listar_documentos,
    montar_dados_documento,
    obter_path_documento,
    obter_tamanho_arquivo,
    resumir_texto_extraido,
    toggle_favorito_documento,
    atualizar_metadados_documento,
)
from app.services.file_service import salvar_arquivo_upload
from app.services.text_extractor import extrair_texto_arquivo
from app.models.user import User

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "title": "Upload de documentos",
            "error_message": None,
            "sucesso": None,
            "erro": None,
            "form_data": {},
            "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    try:
        saved_path = await salvar_arquivo_upload(file)
        extracted_text = extrair_texto_arquivo(saved_path)

        document_data = montar_dados_documento(
            original_filename=file.filename,
            saved_path=saved_path,
            extracted_text=extracted_text,
            user_id=usuario.id,
        )
        documento = criar_documento(db, document_data)

        tamanho_bytes = obter_tamanho_arquivo(documento)

        documento_view = {
            "id": documento.id,
            "original_filename": documento.original_filename,
            "saved_filename": documento.saved_filename,
            "file_path": documento.file_path,
            "file_type": documento.file_type,
            "created_at": documento.created_at,
            "file_exists": documento_existe(documento),
            "file_size_label": formatar_tamanho_arquivo(tamanho_bytes),
            "text_length": contar_caracteres_texto(documento.extracted_text),
            "word_count": contar_palavras_texto(documento.extracted_text),
            "text_preview": resumir_texto_extraido(documento.extracted_text, 500),
            "extracted_text": documento.extracted_text,
            "tags": documento.tags or "",
            "status": documento.status or "",
            "is_favorite": bool(documento.is_favorite),
        }

        return templates.TemplateResponse(
            "document_detail.html",
            {
                "request": request,
                "title": "Detalhes do documento",
                "documento": documento_view,
                "sucesso": "Documento enviado e salvo com sucesso.",
                "erro": None,
            },
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "Upload de documentos",
                "error_message": str(exc),
                "sucesso": None,
                "erro": None,
                "form_data": {},
                "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
            },
            status_code=400,
        )
    except Exception as exc:
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "title": "Upload de documentos",
                "error_message": f"Ocorreu um erro ao processar o arquivo: {exc}",
                "sucesso": None,
                "erro": None,
                "form_data": {},
                "max_upload_size_mb": MAX_UPLOAD_SIZE_MB,
            },
            status_code=500,
        )


@router.get("/", response_class=HTMLResponse)
def documents_list(
    request: Request,
    q: str = Query(""),
    sort: str = Query("recentes"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documentos = listar_documentos(db, usuario.id)

    documentos_view = []
    for documento in documentos:
        tamanho_bytes = obter_tamanho_arquivo(documento)
        documentos_view.append(
            {
                "id": documento.id,
                "original_filename": documento.original_filename,
                "saved_filename": documento.saved_filename,
                "file_type": documento.file_type,
                "created_at": documento.created_at,
                "file_exists": documento_existe(documento),
                "file_size_label": formatar_tamanho_arquivo(tamanho_bytes),
                "text_preview": resumir_texto_extraido(documento.extracted_text, 180),
                "text_length": contar_caracteres_texto(documento.extracted_text),
                "word_count": contar_palavras_texto(documento.extracted_text),
                "tags": documento.tags or "",
                "status": documento.status or "",
                "is_favorite": bool(documento.is_favorite),
            }
        )

    busca = (q or "").strip().lower()
    sort = sort if sort in ORDENACOES_DOCUMENTOS else "recentes"

    if busca:
        documentos_view = [
            documento
            for documento in documentos_view
            if busca in (documento["original_filename"] or "").lower()
            or busca in (documento["saved_filename"] or "").lower()
            or busca in (documento["file_type"] or "").lower()
            or busca in (documento["text_preview"] or "").lower()
            or busca in (documento["tags"] or "").lower()
            or busca in (documento["status"] or "").lower()
        ]

    if sort == "antigos":
        documentos_view.sort(
            key=lambda documento: documento["created_at"] or "",
        )
    elif sort == "nome_az":
        documentos_view.sort(
            key=lambda documento: (documento["original_filename"] or "").lower(),
        )
    elif sort == "nome_za":
        documentos_view.sort(
            key=lambda documento: (documento["original_filename"] or "").lower(),
            reverse=True,
        )
    elif sort == "tipo_az":
        documentos_view.sort(
            key=lambda documento: (
                (documento["file_type"] or "").lower(),
                (documento["original_filename"] or "").lower(),
            ),
        )
    else:
        documentos_view.sort(
            key=lambda documento: documento["created_at"] or "",
            reverse=True,
        )

    total_documentos = len(documentos)
    total_resultados = len(documentos_view)
    total_filtros_ativos = int(bool(busca)) + int(sort != "recentes")

    return templates.TemplateResponse(
        "documents_list.html",
        {
            "request": request,
            "title": "Documentos enviados",
            "documentos": documentos_view,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
            "filtros": {"q": q, "sort": sort},
            "ordenacoes": ORDENACOES_DOCUMENTOS,
            "total_documentos": total_documentos,
            "total_resultados": total_resultados,
            "total_filtros_ativos": total_filtros_ativos,
        },
    )


@router.post("/{document_id}/delete")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documento = buscar_documento_por_id(db, document_id, usuario.id)

    if not documento:
        return RedirectResponse(
            url="/documents?erro=Documento+não+encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        nome_documento = documento.original_filename
        excluir_documento(db, documento)
        return RedirectResponse(
            url=f"/documents?sucesso=Documento+%27{nome_documento}%27+excluído+com+sucesso.",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception:
        return RedirectResponse(
            url="/documents?erro=Não+foi+possível+excluir+o+documento.",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get("/{document_id}", response_class=HTMLResponse)
def document_detail(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documento = buscar_documento_por_id(db, document_id, usuario.id)

    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    tamanho_bytes = obter_tamanho_arquivo(documento)

    documento_view = {
        "id": documento.id,
        "original_filename": documento.original_filename,
        "saved_filename": documento.saved_filename,
        "file_type": documento.file_type,
        "file_path": documento.file_path,
        "created_at": documento.created_at,
        "extracted_text": documento.extracted_text,
        "file_exists": documento_existe(documento),
        "file_size_label": formatar_tamanho_arquivo(tamanho_bytes),
        "text_length": contar_caracteres_texto(documento.extracted_text),
        "word_count": contar_palavras_texto(documento.extracted_text),
        "text_preview": resumir_texto_extraido(documento.extracted_text, 300),
    }

    return templates.TemplateResponse(
        "document_detail.html",
        {
            "request": request,
            "title": "Detalhes do documento",
            "documento": documento_view,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )




@router.post("/{document_id}/favorite")
def toggle_document_favorite(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documento = buscar_documento_por_id(db, document_id, usuario.id)

    if not documento:
        return RedirectResponse(
            url="/documents?erro=Documento+não+encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    documento = toggle_favorito_documento(db, documento)

    mensagem = "Documento favoritado com sucesso." if documento.is_favorite else "Documento removido dos favoritos com sucesso."
    destino = request.headers.get("referer") or "/documents"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{document_id}/metadata")
def update_document_metadata(
    document_id: int,
    request: Request,
    tags: str = Form(""),
    status_value: str = Form("", alias="status"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documento = buscar_documento_por_id(db, document_id, usuario.id)

    if not documento:
        return RedirectResponse(
            url="/documents?erro=Documento+não+encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    atualizar_metadados_documento(
        db,
        documento,
        tags=tags,
        status=status_value,
    )

    destino = request.headers.get("referer") or f"/documents/{document_id}"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso=Metadados+do+documento+atualizados+com+sucesso.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    documento = buscar_documento_por_id(db, document_id, usuario.id)

    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    caminho_arquivo = obter_path_documento(documento)

    if not caminho_arquivo.exists():
        raise HTTPException(
            status_code=404,
            detail="Arquivo não encontrado no armazenamento.",
        )

    return FileResponse(
        path=str(caminho_arquivo),
        filename=documento.original_filename,
        media_type="application/octet-stream",
    )
