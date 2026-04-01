from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.document_service import listar_documentos, listar_documentos_por_ids
from app.services.generation_service import (
    TIPOS_DE_DOCUMENTO,
    atualizar_geracao,
    buscar_geracao_por_id,
    criar_geracao,
    duplicar_geracao,
    desserializar_ids_documentos,
    excluir_geracao,
    gerar_docx_da_geracao,
    gerar_rascunho_juridico,
    listar_geracoes,
    montar_contexto_documental,
    montar_contexto_perfil_escrita,
    resumir_texto,
    serializar_ids_documentos,
    validar_dados_geracao,
    agora_brasil,
    toggle_fixacao_geracao,
)
from app.services.writing_profile_service import (
    buscar_perfil_por_id,
    listar_perfis,
)

router = APIRouter(prefix="/generations", tags=["generations"])
templates = Jinja2Templates(directory="app/templates")


def _parse_selected_document_ids(form) -> list[int]:
    raw_document_ids = form.getlist("document_ids")
    selected_document_ids = []

    for item in raw_document_ids:
        item_str = str(item).strip()
        if item_str.isdigit():
            selected_document_ids.append(int(item_str))

    return selected_document_ids


def _parse_writing_profile_filter(raw_value: str | None) -> tuple[int | None, bool, str]:
    valor = str(raw_value or "").strip()

    if valor == "none":
        return None, True, "none"

    if valor.isdigit():
        return int(valor), False, valor

    return None, False, ""


def _extrair_dados_formulario(form) -> tuple[dict, int | None, list[int]]:
    client_name = str(form.get("client_name", "")).strip()
    document_type = str(form.get("document_type", "")).strip()
    case_subject = str(form.get("case_subject", "")).strip()
    facts = str(form.get("facts", "")).strip()
    requests = str(form.get("requests", "")).strip()
    legal_basis = str(form.get("legal_basis", "")).strip()

    raw_profile_id = str(form.get("writing_profile_id", "")).strip()
    selected_profile_id = int(raw_profile_id) if raw_profile_id.isdigit() else None

    selected_document_ids = _parse_selected_document_ids(form)

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
    }

    return form_data, selected_profile_id, selected_document_ids


def _obter_form_data_da_geracao(geracao) -> dict:
    return {
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis or "",
    }


def _montar_contexto_completo(perfil_escrita, documentos_selecionados: list) -> str:
    contexto_documental = montar_contexto_documental(documentos_selecionados)
    contexto_perfil = montar_contexto_perfil_escrita(perfil_escrita)

    return (
        f"{contexto_perfil}\n\n"
        f"{'=' * 70}\n\n"
        f"{contexto_documental}"
    )


def _montar_item_lista_geracao(geracao) -> dict:
    perfil = geracao.writing_profile
    document_ids = desserializar_ids_documentos(geracao.source_document_ids)

    return {
        "id": geracao.id,
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts_preview": resumir_texto(geracao.facts, 160),
        "requests_preview": resumir_texto(geracao.requests, 160),
        "generated_text_preview": resumir_texto(geracao.generated_text, 260),
        "created_at": geracao.created_at,
        "updated_at": geracao.updated_at,
        "writing_profile_name": perfil.profile_name if perfil else "Sem perfil",
        "document_count": len(document_ids),
        "is_pinned": bool(geracao.is_pinned),
    }


def _render_generation_form(
    request: Request,
    *,
    documentos,
    perfis,
    tipos_de_documento,
    error_message: str | None,
    form_data: dict,
    selected_document_ids: list[int],
    selected_profile_id: int | None,
    modo_edicao: bool,
    geracao=None,
    success_message: str | None = None,
):
    return templates.TemplateResponse(
        "generation_create.html",
        {
            "request": request,
            "title": "Editar geração jurídica" if modo_edicao else "Nova geração jurídica",
            "documentos": documentos,
            "perfis": perfis,
            "tipos_de_documento": tipos_de_documento,
            "error_message": error_message,
            "form_data": form_data,
            "selected_document_ids": selected_document_ids,
            "selected_profile_id": selected_profile_id,
            "sucesso": success_message or request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
            "modo_edicao": modo_edicao,
            "geracao": geracao,
        },
    )


@router.get("/")
def generations_list(request: Request, db: Session = Depends(get_db)):
    search_term = str(request.query_params.get("search", "")).strip()
    client_name = str(request.query_params.get("client_name", "")).strip()
    case_subject = str(request.query_params.get("case_subject", "")).strip()
    document_type = str(request.query_params.get("document_type", "")).strip()
    created_from = str(request.query_params.get("created_from", "")).strip()
    created_to = str(request.query_params.get("created_to", "")).strip()
    sort_by = str(request.query_params.get("sort_by", "updated_desc")).strip() or "updated_desc"

    writing_profile_id, sem_perfil, writing_profile_value = _parse_writing_profile_filter(
        request.query_params.get("writing_profile_id")
    )

    geracoes = listar_geracoes(
        db,
        search_term=search_term,
        client_name=client_name,
        case_subject=case_subject,
        document_type=document_type,
        writing_profile_id=writing_profile_id,
        sem_perfil=sem_perfil,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
    )

    geracoes_view = [_montar_item_lista_geracao(geracao) for geracao in geracoes]
    perfis = listar_perfis(db)

    filtros = {
        "search": search_term,
        "client_name": client_name,
        "case_subject": case_subject,
        "document_type": document_type,
        "writing_profile_id": writing_profile_value,
        "created_from": created_from,
        "created_to": created_to,
        "sort_by": sort_by,
    }

    total_filtros_ativos = sum(
        1
        for valor in [
            filtros["search"],
            filtros["client_name"],
            filtros["case_subject"],
            filtros["document_type"],
            filtros["writing_profile_id"],
            filtros["created_from"],
            filtros["created_to"],
            filtros["sort_by"] if filtros["sort_by"] != "updated_desc" else "",
        ]
        if valor
    )

    ordenacoes = {
        "updated_desc": "Mais recentemente atualizadas",
        "updated_asc": "Menos recentemente atualizadas",
        "created_desc": "Mais recentes primeiro",
        "created_asc": "Mais antigas primeiro",
        "client_name_asc": "Cliente (A-Z)",
        "client_asc": "Cliente (A-Z)",
        "client_desc": "Cliente (Z-A)",
    }

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "geracoes": geracoes_view,
            "perfis": perfis,
            "filtros": filtros,
            "ordenacoes": ordenacoes,
            "total_resultados": len(geracoes_view),
            "total_filtros_ativos": total_filtros_ativos,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )




@router.post("/{generation_id}/toggle-pin")
def toggle_pin_generation(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = toggle_fixacao_geracao(db, generation_id)

    if not geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada.')}",
            status_code=303,
        )

    mensagem = "Geração fixada com sucesso." if geracao.is_pinned else "Geração desfixada com sucesso."
    destino = request.headers.get("referer") or "/generations"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=303,
    )


@router.get("/create")
def create_generation_page(request: Request, db: Session = Depends(get_db)):
    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    selected_profile_id = None
    form_data = {}
    selected_document_ids = []
    success_message = None

    duplicate_from = str(request.query_params.get("duplicate_from", "")).strip()
    if duplicate_from.isdigit():
        geracao_origem = buscar_geracao_por_id(db, int(duplicate_from))
        if geracao_origem:
            form_data = _obter_form_data_da_geracao(geracao_origem)
            selected_document_ids = desserializar_ids_documentos(geracao_origem.source_document_ids)
            selected_profile_id = geracao_origem.writing_profile_id
            success_message = f"Base da geração #{geracao_origem.id} carregada para duplicação."

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        error_message=None,
        form_data=form_data,
        selected_document_ids=selected_document_ids,
        selected_profile_id=selected_profile_id,
        modo_edicao=False,
        geracao=None,
        success_message=success_message,
    )


@router.post("/create")
async def create_generation(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    form_data, selected_profile_id, selected_document_ids = _extrair_dados_formulario(form)

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    try:
        dados_validados = validar_dados_geracao(**form_data)
    except ValueError as exc:
        return _render_generation_form(
            request,
            documentos=documentos,
            perfis=perfis,
            tipos_de_documento=TIPOS_DE_DOCUMENTO,
            error_message=str(exc),
            form_data=form_data,
            selected_document_ids=selected_document_ids,
            selected_profile_id=selected_profile_id,
            modo_edicao=False,
            geracao=None,
        )

    documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)

    perfil_escrita = None
    if selected_profile_id is not None:
        perfil_escrita = buscar_perfil_por_id(db, selected_profile_id)

    context_used = _montar_contexto_completo(perfil_escrita, documentos_selecionados)

    generated_text = gerar_rascunho_juridico(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
    )

    nova_geracao = criar_geracao(
        db=db,
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
        generated_text=generated_text,
        writing_profile_id=selected_profile_id,
        source_document_ids=serializar_ids_documentos(selected_document_ids),
    )

    return RedirectResponse(
        url=f"/generations/{nova_geracao.id}?sucesso={quote('Geração criada com sucesso.')}",
        status_code=303,
    )


@router.get("/{generation_id}")
def generation_detail(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada")

    document_ids = desserializar_ids_documentos(geracao.source_document_ids)
    documentos = listar_documentos_por_ids(db, document_ids)

    geracao_view = {
        "id": geracao.id,
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis,
        "generated_text": geracao.generated_text,
        "context_used": geracao.context_used,
        "created_at": geracao.created_at,
        "updated_at": geracao.updated_at,
        "writing_profile_name": geracao.writing_profile.profile_name if geracao.writing_profile else "Sem perfil",
        "documentos": documentos,
        "document_count": len(document_ids),
        "is_pinned": bool(geracao.is_pinned),
    }

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "geracao": geracao_view,
            "documentos_base": documentos,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("/{generation_id}/edit")
def edit_generation_page(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada para edição.')}",
            status_code=303,
        )

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)
    selected_document_ids = desserializar_ids_documentos(geracao.source_document_ids)
    form_data = _obter_form_data_da_geracao(geracao)

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        error_message=None,
        form_data=form_data,
        selected_document_ids=selected_document_ids,
        selected_profile_id=geracao.writing_profile_id,
        modo_edicao=True,
        geracao=geracao,
    )


@router.post("/{generation_id}/edit")
async def edit_generation(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada para edição.')}",
            status_code=303,
        )

    form = await request.form()

    form_data, selected_profile_id, selected_document_ids = _extrair_dados_formulario(form)

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    try:
        dados_validados = validar_dados_geracao(**form_data)
    except ValueError as exc:
        return _render_generation_form(
            request,
            documentos=documentos,
            perfis=perfis,
            tipos_de_documento=TIPOS_DE_DOCUMENTO,
            error_message=str(exc),
            form_data=form_data,
            selected_document_ids=selected_document_ids,
            selected_profile_id=selected_profile_id,
            modo_edicao=True,
            geracao=geracao,
        )

    documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)

    perfil_escrita = None
    if selected_profile_id is not None:
        perfil_escrita = buscar_perfil_por_id(db, selected_profile_id)

    context_used = _montar_contexto_completo(perfil_escrita, documentos_selecionados)

    generated_text = gerar_rascunho_juridico(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
    )

    atualizar_geracao(
        db=db,
        geracao=geracao,
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
        generated_text=generated_text,
        writing_profile_id=selected_profile_id,
        source_document_ids=serializar_ids_documentos(selected_document_ids),
    )

    return RedirectResponse(
        url=f"/generations/{generation_id}?sucesso={quote('Geração atualizada com sucesso.')}",
        status_code=303,
    )


@router.post("/{generation_id}/save-text")
async def save_generation_text(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada.')}",
            status_code=303,
        )

    form = await request.form()
    generated_text = str(form.get("generated_text", "")).strip()

    if not generated_text:
        return RedirectResponse(
            url=f"/generations/{generation_id}?erro={quote('O texto jurídico não pode ficar vazio.')}",
            status_code=303,
        )

    geracao.generated_text = generated_text
    geracao.updated_at = agora_brasil()
    db.add(geracao)
    db.commit()
    db.refresh(geracao)

    return RedirectResponse(
        url=f"/generations/{generation_id}?sucesso={quote('Versão ajustada salva com sucesso.')}",
        status_code=303,
    )


@router.get("/{generation_id}/download-txt")
def download_generation_txt(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada")

    nome_arquivo = f"geracao_juridica_{geracao.id}.txt"
    headers = {
        "Content-Disposition": f'attachment; filename="{nome_arquivo}"'
    }

    return Response(
        content=(geracao.generated_text or ""),
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )


@router.post("/{generation_id}/duplicate")
def duplicate_generation(generation_id: int, db: Session = Depends(get_db)):
    nova_geracao = duplicar_geracao(db, generation_id)

    if not nova_geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada para duplicação.')}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/generations/{nova_geracao.id}?sucesso={quote(f'Geração #{generation_id} duplicada com sucesso.')}",
        status_code=303,
    )


@router.post("/{generation_id}/delete")
def delete_generation(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        return RedirectResponse(
            url=f"/generations?erro={quote('Geração não encontrada para exclusão.')}",
            status_code=303,
        )

    excluir_geracao(db, generation_id)

    return RedirectResponse(
        url=f"/generations?sucesso={quote('Geração excluída com sucesso.')}",
        status_code=303,
    )


@router.get("/{generation_id}/download-docx")
def download_generation_docx(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada")

    arquivo = gerar_docx_da_geracao(geracao)
    nome_arquivo = f"geracao_juridica_{geracao.id}.docx"

    headers = {
        "Content-Disposition": f'attachment; filename="{nome_arquivo}"'
    }

    return Response(
        content=arquivo.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )