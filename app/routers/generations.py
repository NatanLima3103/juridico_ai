from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
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
)
from app.services.writing_profile_service import (
    buscar_perfil_ativo,
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


def _montar_contexto_completo(perfil_escrita, documentos_selecionados: list) -> str:
    contexto_documental = montar_contexto_documental(documentos_selecionados)
    contexto_perfil = montar_contexto_perfil_escrita(perfil_escrita)

    return (
        f"{contexto_perfil}\n\n"
        f"{'=' * 70}\n\n"
        f"{contexto_documental}"
    )


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
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
            "modo_edicao": modo_edicao,
            "geracao": geracao,
        },
    )


@router.get("/")
def generations_list(request: Request, db: Session = Depends(get_db)):
    geracoes = listar_geracoes(db)

    geracoes_view = []
    for geracao in geracoes:
        perfil = geracao.writing_profile

        geracoes_view.append(
            {
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
            }
        )

    return templates.TemplateResponse(
        "generations_list.html",
        {
            "request": request,
            "title": "Histórico de gerações",
            "geracoes": geracoes_view,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("/create")
def create_generation_page(request: Request, db: Session = Depends(get_db)):
    documentos = listar_documentos(db)
    perfis = listar_perfis(db)
    perfil_ativo = buscar_perfil_ativo(db)

    selected_profile_id = perfil_ativo.id if perfil_ativo else None

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        error_message=None,
        form_data={},
        selected_document_ids=[],
        selected_profile_id=selected_profile_id,
        modo_edicao=False,
        geracao=None,
    )


@router.post("/create")
async def create_generation(request: Request, db: Session = Depends(get_db)):
    form = await request.form()

    client_name = str(form.get("client_name", "")).strip()
    document_type = str(form.get("document_type", "")).strip()
    case_subject = str(form.get("case_subject", "")).strip()
    facts = str(form.get("facts", "")).strip()
    requests = str(form.get("requests", "")).strip()
    legal_basis = str(form.get("legal_basis", "")).strip()

    raw_profile_id = str(form.get("writing_profile_id", "")).strip()
    selected_profile_id = int(raw_profile_id) if raw_profile_id.isdigit() else None

    selected_document_ids = _parse_selected_document_ids(form)

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
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
        )

    documentos_selecionados = listar_documentos_por_ids(db, selected_document_ids)

    if not documentos_selecionados:
        return _render_generation_form(
            request,
            documentos=documentos,
            perfis=perfis,
            tipos_de_documento=TIPOS_DE_DOCUMENTO,
            error_message="Selecione pelo menos um documento base.",
            form_data=form_data,
            selected_document_ids=selected_document_ids,
            selected_profile_id=selected_profile_id,
            modo_edicao=False,
            geracao=None,
        )

    perfil_escrita = None
    if selected_profile_id:
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
        writing_profile=perfil_escrita,
        documentos_selecionados=documentos_selecionados,
    )

    geracao = criar_geracao(
        db=db,
        client_name=dados_validados["client_name"],
        document_type=dados_validados["document_type"],
        case_subject=dados_validados["case_subject"],
        facts=dados_validados["facts"],
        requests=dados_validados["requests"],
        legal_basis=dados_validados["legal_basis"],
        context_used=context_used,
        generated_text=generated_text,
        writing_profile_id=perfil_escrita.id if perfil_escrita else None,
        source_document_ids=serializar_ids_documentos(selected_document_ids),
    )

    return RedirectResponse(
        url=f"/generations/{geracao.id}?sucesso=Geração criada com sucesso.",
        status_code=303,
    )


@router.get("/{generation_id}")
def generation_detail(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    document_ids = desserializar_ids_documentos(geracao.source_document_ids)
    documentos_base = listar_documentos_por_ids(db, document_ids) if document_ids else []

    return templates.TemplateResponse(
        "generation_detail.html",
        {
            "request": request,
            "title": "Detalhes da geração",
            "geracao": geracao,
            "documentos_base": documentos_base,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
        },
    )


@router.get("/{generation_id}/edit")
def edit_generation_page(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    form_data = {
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis or "",
    }

    selected_document_ids = desserializar_ids_documentos(geracao.source_document_ids)
    selected_profile_id = geracao.writing_profile_id

    return _render_generation_form(
        request,
        documentos=documentos,
        perfis=perfis,
        tipos_de_documento=TIPOS_DE_DOCUMENTO,
        error_message=None,
        form_data=form_data,
        selected_document_ids=selected_document_ids,
        selected_profile_id=selected_profile_id,
        modo_edicao=True,
        geracao=geracao,
    )


@router.post("/{generation_id}/edit")
async def edit_generation(
    generation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    form = await request.form()

    client_name = str(form.get("client_name", "")).strip()
    document_type = str(form.get("document_type", "")).strip()
    case_subject = str(form.get("case_subject", "")).strip()
    facts = str(form.get("facts", "")).strip()
    requests = str(form.get("requests", "")).strip()
    legal_basis = str(form.get("legal_basis", "")).strip()

    raw_profile_id = str(form.get("writing_profile_id", "")).strip()
    selected_profile_id = int(raw_profile_id) if raw_profile_id.isdigit() else None

    selected_document_ids = _parse_selected_document_ids(form)

    documentos = listar_documentos(db)
    perfis = listar_perfis(db)

    form_data = {
        "client_name": client_name,
        "document_type": document_type,
        "case_subject": case_subject,
        "facts": facts,
        "requests": requests,
        "legal_basis": legal_basis,
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

    if not documentos_selecionados:
        return _render_generation_form(
            request,
            documentos=documentos,
            perfis=perfis,
            tipos_de_documento=TIPOS_DE_DOCUMENTO,
            error_message="Selecione pelo menos um documento base.",
            form_data=form_data,
            selected_document_ids=selected_document_ids,
            selected_profile_id=selected_profile_id,
            modo_edicao=True,
            geracao=geracao,
        )

    perfil_escrita = None
    if selected_profile_id:
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
        writing_profile_id=perfil_escrita.id if perfil_escrita else None,
        source_document_ids=serializar_ids_documentos(selected_document_ids),
    )

    return RedirectResponse(
        url=f"/generations/{geracao.id}?sucesso=Geração atualizada com sucesso.",
        status_code=303,
    )


@router.get("/{generation_id}/download-txt")
def download_generation_txt(
    generation_id: int,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    nome_cliente = (geracao.client_name or "cliente").strip().replace(" ", "_")
    tipo_documento = (geracao.document_type or "documento").strip().replace(" ", "_")
    nome_arquivo = f"juridico_ai_{tipo_documento}_{nome_cliente}_{geracao.id}.txt"
    nome_arquivo_codificado = quote(nome_arquivo)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{nome_arquivo_codificado}"
    }

    return Response(
        content=geracao.generated_text,
        media_type="text/plain; charset=utf-8",
        headers=headers,
    )


@router.get("/{generation_id}/download-docx")
def download_generation_docx(
    generation_id: int,
    db: Session = Depends(get_db),
):
    geracao = buscar_geracao_por_id(db, generation_id)

    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")

    nome_cliente = (geracao.client_name or "cliente").strip().replace(" ", "_")
    tipo_documento = (geracao.document_type or "documento").strip().replace(" ", "_")
    nome_arquivo = f"juridico_ai_{tipo_documento}_{nome_cliente}_{geracao.id}.docx"
    nome_arquivo_codificado = quote(nome_arquivo)

    conteudo_docx = gerar_docx_da_geracao(geracao)

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{nome_arquivo_codificado}"
    }

    return Response(
        content=conteudo_docx,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.post("/{generation_id}/delete")
def delete_generation(
    generation_id: int,
    db: Session = Depends(get_db),
):
    sucesso = excluir_geracao(db, generation_id)

    if not sucesso:
        return RedirectResponse(
            url="/generations/?erro=Geração não encontrada.",
            status_code=303,
        )

    return RedirectResponse(
        url="/generations/?sucesso=Geração excluída com sucesso.",
        status_code=303,
    )