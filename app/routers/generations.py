from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.common import templates
from app.services.document_service import listar_documentos, listar_documentos_por_ids
from app.services.generation_service import (
    TIPOS_DE_DOCUMENTO,
    alternar_favorito_geracao,
    alternar_fixacao_geracao,
    aplicar_template_juridico_pronto,
    atualizar_geracao,
    buscar_geracao_por_id,
    criar_geracao,
    excluir_geracao,
    gerar_docx_da_geracao,
    gerar_txt_da_geracao,
    gerar_rascunho_juridico,
    coletar_ids_inteiros_unicos,
    contar_filtros_ativos_geracoes,
    listar_geracoes,
    listar_templates_juridicos_prontos,
    montar_resumo_geracao,
    montar_contexto_inteligente,
    normalizar_filtros_listagem,
    serializar_filtros_geracao_para_template,
    serializar_ids_documentos,
    validar_dados_geracao,
)
from app.services.writing_profile_service import (
    buscar_perfil_por_id,
    listar_perfis_escrita,
)

router = APIRouter(prefix="/generations", tags=["generations"])


ORDENACOES_GERACOES = {
    "updated_desc": "Atualização (mais recente primeiro)",
    "updated_asc": "Atualização (mais antiga primeiro)",
    "created_desc": "Criação (mais recente primeiro)",
    "created_asc": "Criação (mais antiga primeiro)",
    "client_asc": "Cliente (A-Z)",
    "client_desc": "Cliente (Z-A)",
}


def _to_int_list(values: list[str] | None) -> list[int]:
    return coletar_ids_inteiros_unicos(values)


def _resumir_texto(texto: str | None, limite: int = 140) -> str:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return "—"

    if len(texto_limpo) <= limite:
        return texto_limpo

    return texto_limpo[:limite].rstrip(" .,;:") + "..."


def _contar_filtros_ativos(filtros: dict) -> int:
    return contar_filtros_ativos_geracoes(filtros)


def _generation_to_dict(geracao):
    return montar_resumo_geracao(geracao)


def _serialize_filters_for_template(filtros: dict) -> dict:
    return serializar_filtros_geracao_para_template(filtros)


def _render_generation_form(
    request: Request,
    *,
    documentos,
    perfis,
    tipos_de_documento,
    error_message: str | None = None,
    form_data: dict | None = None,
    selected_document_ids: list[int] | None = None,
    selected_profile_id: int | None = None,
    modo_edicao: bool = False,
    geracao=None,
    duplicate_mode: bool = False,
    duplicate_source_id: int | None = None,
):
    form_data = form_data or {}
    selected_document_ids = selected_document_ids or []

    if selected_profile_id is not None:
        form_data["writing_profile_id"] = str(selected_profile_id)

    form_data["document_ids"] = [str(document_id) for document_id in selected_document_ids]

    if modo_edicao:
        title = "Editar geração"
        subtitle = "Atualize os dados e regenere a minuta mantendo a geração existente."
        submit_label = "Salvar alterações"
        submit_loading_text = "Salvando..."
        action_url = f"/generations/{geracao.id}/edit"
    elif duplicate_mode:
        title = "Duplicar e regenerar"
        subtitle = "Revise os dados abaixo e crie uma nova geração com base na anterior."
        submit_label = "Duplicar e regenerar"
        submit_loading_text = "Duplicando..."
        action_url = "/generations/create"
    else:
        title = "Nova geração jurídica"
        subtitle = "Preencha os dados abaixo para gerar uma nova minuta."
        submit_label = "Gerar minuta"
        submit_loading_text = "Gerando..."
        action_url = "/generations/create"

    return templates.TemplateResponse(
        "generation_create.html",
        {
            "request": request,
            "title": title,
            "subtitle": subtitle,
            "documentos": documentos,
            "perfis": perfis,
            "tipos_de_documento": tipos_de_documento,
            "error_message": error_message,
            "form_data": form_data,
            "selected_document_ids": selected_document_ids,
            "selected_profile_id": selected_profile_id,
            "modo_edicao": modo_edicao,
            "geracao": geracao,
            "submit_label": submit_label,
            "submit_loading_text": submit_loading_text,
            "action_url": action_url,
            "duplicate_mode": duplicate_mode,
            "duplicate_source_id": duplicate_source_id,
            "templates_prontos": listar_templates_juridicos_prontos(),
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("")
async def list_generations(
    request: Request,
    search: str = "",
    search_term: str = "",
    document_type: str = "",
    writing_profile_id: str = "",
    client_name: str = "",
    case_subject: str = "",
    created_from: str = "",
    created_to: str = "",
    sort_by: str = "updated_desc",
    sucesso: str | None = None,
    erro: str | None = None,
    db: Session = Depends(get_db),
):
    termo_busca = (search or search_term or "").strip()

    sem_perfil = False
    profile_id_int: int | None = None

    if writing_profile_id == "none":
        sem_perfil = True
    elif writing_profile_id:
        try:
            profile_id_int = int(writing_profile_id)
        except ValueError:
            profile_id_int = None

    filtros = normalizar_filtros_listagem(
        search_term=termo_busca,
        document_type=document_type,
        writing_profile_id=profile_id_int,
        sem_perfil=sem_perfil,
        client_name=client_name,
        case_subject=case_subject,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
    )

    geracoes = listar_geracoes(db, filtros=filtros)
    perfis = listar_perfis_escrita(db)

    geracoes_template = [montar_resumo_geracao(geracao) for geracao in geracoes]
    filtros_template = serializar_filtros_geracao_para_template(filtros)
    total_resultados = len(geracoes_template)
    total_filtros_ativos = contar_filtros_ativos_geracoes(filtros)

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "geracoes": geracoes_template,
            "perfis": perfis,
            "tipos_de_documento": TIPOS_DE_DOCUMENTO,
            "filtros": filtros_template,
            "ordenacoes": ORDENACOES_GERACOES,
            "total_resultados": total_resultados,
            "total_filtros_ativos": total_filtros_ativos,
            "sucesso": sucesso,
            "erro": erro,
        },
    )


@router.get("/create")
async def create_generation_form(
    request: Request,
    db: Session = Depends(get_db),
):
    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        form_data={},
        selected_document_ids=[],
        selected_profile_id=None,
    )


@router.get("/{generation_id}")
async def generation_detail(
    generation_id: int,
    request: Request,
    sucesso: str | None = None,
    erro: str | None = None,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    documento_ids = geracao.document_ids
    documentos_base = listar_documentos_por_ids(db, documento_ids)

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "geracao": montar_resumo_geracao(geracao),
            "documentos_base": documentos_base,
            "sucesso": sucesso,
            "erro": erro,
        },
    )


@router.get("/{generation_id}/edit")
async def edit_generation_form(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    form_data = {
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis,
        "tags": geracao.tags or "",
        "status": geracao.status or "",
        "is_favorite": bool(geracao.is_favorite),
    }

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        form_data=form_data,
        selected_document_ids=geracao.document_ids,
        selected_profile_id=geracao.writing_profile_id,
        modo_edicao=True,
        geracao=geracao,
    )


@router.get("/{generation_id}/duplicate")
async def duplicate_generation_form(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    form_data = {
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis,
        "tags": geracao.tags or "",
        "status": geracao.status or "",
        "is_favorite": bool(geracao.is_favorite),
    }

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        form_data=form_data,
        selected_document_ids=geracao.document_ids,
        selected_profile_id=geracao.writing_profile_id,
        duplicate_mode=True,
        duplicate_source_id=geracao.id,
    )


@router.post("/create")
async def create_generation(
    request: Request,
    client_name: str = Form(...),
    document_type: str = Form(...),
    case_subject: str = Form(...),
    facts: str = Form(...),
    requests: str = Form(...),
    legal_basis: str = Form(""),
    tags: str = Form(""),
    status_value: str = Form("", alias="status"),
    is_favorite: str | None = Form(None),
    document_ids: list[str] | None = Form(None),
    writing_profile_id: str | None = Form(None),
    duplicate_mode: str | None = Form(None),
    duplicate_source_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    selected_document_ids = coletar_ids_inteiros_unicos(document_ids)

    selected_profile_id = None
    if writing_profile_id and str(writing_profile_id).strip():
        try:
            selected_profile_id = int(writing_profile_id)
        except ValueError:
            selected_profile_id = None

    duplicate_mode_bool = str(duplicate_mode or "").strip().lower() == "true"

    duplicate_source_id_int = None
    if duplicate_source_id and str(duplicate_source_id).strip():
        try:
            duplicate_source_id_int = int(duplicate_source_id)
        except ValueError:
            duplicate_source_id_int = None

    is_favorite_bool = str(is_favorite or "").strip().lower() == "true"

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
        "tags": tags,
        "status": status_value,
        "is_favorite": is_favorite_bool,
    }

    try:
        dados_validados = validar_dados_geracao(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis,
        )
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
            duplicate_mode=duplicate_mode_bool,
            duplicate_source_id=duplicate_source_id_int,
        )

    documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)

    perfil_escrita = None
    if selected_profile_id is not None:
        perfil_escrita = buscar_perfil_por_id(db, selected_profile_id)

    context_used = montar_contexto_inteligente(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        writing_profile=perfil_escrita,
        documentos_selecionados=documentos_selecionados,
    )

    generated_text = gerar_rascunho_juridico(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
        writing_profile=perfil_escrita,
        documentos_selecionados=documentos_selecionados,
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
        tags=tags,
        status=status_value,
        is_favorite=is_favorite_bool,
    )

    if duplicate_mode_bool and duplicate_source_id_int is not None:
        mensagem_sucesso = f"Geração #{duplicate_source_id_int} duplicada e regenerada com sucesso."
    else:
        mensagem_sucesso = "Geração criada com sucesso."

    return RedirectResponse(
        url=f"/generations/{nova_geracao.id}?sucesso={quote(mensagem_sucesso)}",
        status_code=303,
    )


@router.post("/{generation_id}/edit")
async def edit_generation(
    generation_id: int,
    request: Request,
    client_name: str = Form(...),
    document_type: str = Form(...),
    case_subject: str = Form(...),
    facts: str = Form(...),
    requests: str = Form(...),
    legal_basis: str = Form(""),
    tags: str = Form(""),
    status_value: str = Form("", alias="status"),
    document_ids: list[str] | None = Form(None),
    writing_profile_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    selected_document_ids = coletar_ids_inteiros_unicos(document_ids)

    selected_profile_id = None
    if writing_profile_id and str(writing_profile_id).strip():
        try:
            selected_profile_id = int(writing_profile_id)
        except ValueError:
            selected_profile_id = None

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
        "tags": tags,
        "status": status_value,
        "is_favorite": bool(geracao.is_favorite),
    }

    try:
        dados_validados = validar_dados_geracao(
            client_name=client_name,
            document_type=document_type,
            case_subject=case_subject,
            facts=facts,
            requests=requests,
            legal_basis=legal_basis,
        )
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

    context_used = montar_contexto_inteligente(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        writing_profile=perfil_escrita,
        documentos_selecionados=documentos_selecionados,
    )

    generated_text = gerar_rascunho_juridico(
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
        writing_profile=perfil_escrita,
        documentos_selecionados=documentos_selecionados,
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
        tags=tags,
        status=status_value,
    )

    return RedirectResponse(
        url=f"/generations/{generation_id}?sucesso={quote('Geração atualizada com sucesso.')}",
        status_code=303,
    )


@router.post("/{generation_id}/save-text")
async def save_generation_text(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    form = await request.form()
    generated_text = str(form.get("generated_text") or "").strip()

    if not generated_text:
        return RedirectResponse(
            url=f"/generations/{generation_id}?erro={quote('O texto jurídico não pode ficar vazio.')}",
            status_code=303,
        )

    geracao.generated_text = generated_text
    db.add(geracao)
    db.commit()

    return RedirectResponse(
        url=f"/generations/{generation_id}?sucesso={quote('Versão ajustada salva com sucesso.')}",
        status_code=303,
    )


@router.post("/{generation_id}/delete")
async def delete_generation(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    excluir_geracao(db, geracao)
    return RedirectResponse(
        url=f"/generations?sucesso={quote('Geração excluída com sucesso.')}",
        status_code=303,
    )


@router.post("/{generation_id}/toggle-pin")
async def toggle_pin_generation(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    geracao = alternar_fixacao_geracao(db, geracao)

    mensagem = "Geração fixada com sucesso." if geracao.is_pinned else "Geração desfixada com sucesso."
    destino = request.headers.get("referer") or "/generations"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=303,
    )


@router.post("/{generation_id}/toggle-favorite")
async def toggle_favorite_generation(generation_id: int, request: Request, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    geracao = alternar_favorito_geracao(db, geracao)

    mensagem = "Geração favoritada com sucesso." if geracao.is_favorite else "Geração removida dos favoritos com sucesso."
    destino = request.headers.get("referer") or "/generations"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=303,
    )


@router.post("/apply-template")
async def apply_template_to_generation_form(
    request: Request,
    template_document_type: str = Form(...),
    client_name: str = Form(""),
    case_subject: str = Form(""),
    facts: str = Form(""),
    requests: str = Form(""),
    legal_basis: str = Form(""),
    tags: str = Form(""),
    status_value: str = Form("", alias="status"),
    is_favorite: str | None = Form(None),
    writing_profile_id: str | None = Form(None),
    document_ids: list[str] | None = Form(None),
    duplicate_mode: str | None = Form(None),
    duplicate_source_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    documentos = listar_documentos(db)
    perfis = listar_perfis_escrita(db)

    selected_document_ids = coletar_ids_inteiros_unicos(document_ids)

    selected_profile_id = None
    if writing_profile_id and str(writing_profile_id).strip():
        try:
            selected_profile_id = int(writing_profile_id)
        except ValueError:
            selected_profile_id = None

    duplicate_mode_bool = str(duplicate_mode or "").strip().lower() == "true"

    duplicate_source_id_int = None
    if duplicate_source_id and str(duplicate_source_id).strip():
        try:
            duplicate_source_id_int = int(duplicate_source_id)
        except ValueError:
            duplicate_source_id_int = None

    is_favorite_bool = str(is_favorite or "").strip().lower() == "true"

    form_data = {
        "client_name": client_name,
        "document_type": template_document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
        "tags": tags,
        "status": status_value,
        "is_favorite": is_favorite_bool,
    }

    try:
        dados_template = aplicar_template_juridico_pronto(template_document_type)
        form_data.update(
            {
                "document_type": dados_template["document_type"],
                "case_subject": dados_template["case_subject"],
                "facts": dados_template["facts"],
                "requests": dados_template["requests"],
                "legal_basis": dados_template["legal_basis"],
            }
        )
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
            duplicate_mode=duplicate_mode_bool,
            duplicate_source_id=duplicate_source_id_int,
        )

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        form_data=form_data,
        selected_document_ids=selected_document_ids,
        selected_profile_id=selected_profile_id,
        duplicate_mode=duplicate_mode_bool,
        duplicate_source_id=duplicate_source_id_int,
    )


@router.get("/{generation_id}/download-docx")
async def download_generation_docx(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    arquivo = gerar_docx_da_geracao(geracao)
    nome_arquivo = f"geracao_{geracao.id}.docx"

    return Response(
        content=arquivo,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )


@router.get("/{generation_id}/download-txt")
async def download_generation_txt(generation_id: int, db: Session = Depends(get_db)):
    geracao = buscar_geracao_por_id(db, generation_id)
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    arquivo = gerar_txt_da_geracao(geracao)
    nome_arquivo = f"geracao_{geracao.id}.txt"

    return Response(
        content=arquivo,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
