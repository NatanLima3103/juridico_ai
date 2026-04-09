from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_authenticated_user
from app.models.user import User
from app.routers.common import templates
from app.schemas.writing_profile import WritingProfileCreate
from app.services.generation_service import resumir_texto
from app.services.writing_profile_service import (
    atualizar_perfil,
    buscar_perfil_por_id,
    contar_filtros_ativos_perfis,
    criar_perfil,
    duplicar_perfil,
    excluir_perfil,
    listar_perfis_filtrados,
    montar_resumo_perfil,
    normalizar_filtros_perfis,
    obter_ordenacoes_perfis,
    obter_tons_disponiveis,
    toggle_favorito_perfil,
    toggle_fixacao_perfil,
    validar_dados_perfil,
)

router = APIRouter(
    prefix="/writing-profiles",
    tags=["writing_profiles"],
    dependencies=[Depends(get_authenticated_user)],
)


@router.get("")
def listar_perfis_page(
    request: Request,
    search: str = Query(""),
    profile_name: str = Query(""),
    lawyer_name: str = Query(""),
    office_name: str = Query(""),
    tone: str = Query(""),
    created_from: str = Query(""),
    created_to: str = Query(""),
    sort_by: str = Query("created_desc"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    filtros = normalizar_filtros_perfis(
        search=search,
        profile_name=profile_name,
        lawyer_name=lawyer_name,
        office_name=office_name,
        tone=tone,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
    )

    perfis = listar_perfis_filtrados(db, usuario.id, filtros)
    tons_disponiveis = obter_tons_disponiveis(db, usuario.id)
    ordenacoes = obter_ordenacoes_perfis()
    total_filtros_ativos = contar_filtros_ativos_perfis(filtros)

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
            "profiles": perfis_resumo,
            "sucesso": request.query_params.get("sucesso"),
            "erro": request.query_params.get("erro"),
            "filtros": filtros,
            "tons_disponiveis": tons_disponiveis,
            "tones": tons_disponiveis,
            "ordenacoes": ordenacoes,
            "total_resultados": len(perfis_resumo),
            "total_filtros_ativos": total_filtros_ativos,
        },
    )


@router.post("/{profile_id}/toggle-pin")
def toggle_pin_profile(profile_id: int, request: Request, db: Session = Depends(get_db), usuario: User = Depends(get_authenticated_user)):
    perfil = toggle_fixacao_perfil(db, profile_id, usuario.id)

    if not perfil:
        return RedirectResponse(
            url=f"/writing-profiles?erro={quote('Perfil não encontrado.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    mensagem = "Perfil fixado com sucesso." if perfil.is_pinned else "Perfil desfixado com sucesso."
    destino = request.headers.get("referer") or "/writing-profiles"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{profile_id}/toggle-favorite")
def toggle_favorite_profile(profile_id: int, request: Request, db: Session = Depends(get_db), usuario: User = Depends(get_authenticated_user)):
    perfil = toggle_favorito_perfil(db, profile_id, usuario.id)

    if not perfil:
        return RedirectResponse(
            url=f"/writing-profiles?erro={quote('Perfil não encontrado.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    mensagem = "Perfil favoritado com sucesso." if perfil.is_favorite else "Perfil removido dos favoritos com sucesso."
    destino = request.headers.get("referer") or "/writing-profiles"
    separador = "&" if "?" in destino else "?"

    return RedirectResponse(
        url=f"{destino}{separador}sucesso={quote(mensagem)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/create")
def exibir_formulario_perfil(request: Request):
    return templates.TemplateResponse(
        "writing_profile_form.html",
        {
            "request": request,
            "erro": None,
            "form_data": {},
            "modo_edicao": False,
            "perfil_id": None,
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
    tags: str = Form(""),
    is_favorite: bool = Form(False),
    status_value: str = Form("", alias="status"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
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
            tags=tags,
            is_favorite=is_favorite,
            status=status_value,
        )

        payload = WritingProfileCreate(user_id=usuario.id, **dados)
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
                    "tags": tags,
                    "is_favorite": is_favorite,
                    "status": status_value,
                },
                "modo_edicao": False,
                "perfil_id": None,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.get("/{profile_id}/edit")
def exibir_formulario_edicao_perfil(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    perfil = buscar_perfil_por_id(db, profile_id, usuario.id)

    if not perfil:
        return RedirectResponse(
            url="/writing-profiles?erro=Perfil não encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        "writing_profile_form.html",
        {
            "request": request,
            "erro": None,
            "form_data": {
                "profile_name": perfil.profile_name,
                "tone": perfil.tone,
                "lawyer_name": perfil.lawyer_name or "",
                "office_name": perfil.office_name or "",
                "qualification_style": perfil.qualification_style or "",
                "opening_phrase": perfil.opening_phrase or "",
                "request_intro": perfil.request_intro or "",
                "closing_phrase": perfil.closing_phrase or "",
                "legal_style_notes": perfil.legal_style_notes or "",
                "recurring_expressions": perfil.recurring_expressions or "",
                "tags": perfil.tags or "",
                "is_favorite": bool(perfil.is_favorite),
                "status": perfil.status or "",
            },
            "modo_edicao": True,
            "perfil_id": perfil.id,
        },
    )


@router.post("/{profile_id}/edit")
def editar_perfil_page(
    profile_id: int,
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
    tags: str = Form(""),
    is_favorite: bool = Form(False),
    status_value: str = Form("", alias="status"),
    db: Session = Depends(get_db),
    usuario: User = Depends(get_authenticated_user),
):
    perfil = buscar_perfil_por_id(db, profile_id, usuario.id)

    if not perfil:
        return RedirectResponse(
            url="/writing-profiles?erro=Perfil não encontrado.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

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
            tags=tags,
            is_favorite=is_favorite,
            status=status_value,
        )

        payload = WritingProfileCreate(user_id=usuario.id, **dados)
        atualizar_perfil(db, profile_id, usuario.id, payload)

        return RedirectResponse(
            url="/writing-profiles?sucesso=Perfil atualizado com sucesso.",
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
                    "tags": tags,
                    "is_favorite": is_favorite,
                    "status": status_value,
                },
                "modo_edicao": True,
                "perfil_id": profile_id,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@router.post("/{profile_id}/duplicate")
def duplicar_perfil_page(profile_id: int, db: Session = Depends(get_db), usuario: User = Depends(get_authenticated_user)):
    novo_perfil = duplicar_perfil(db, profile_id, usuario.id)

    if not novo_perfil:
        return RedirectResponse(
            url=f"/writing-profiles?erro={quote('Perfil não encontrado para duplicação.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/writing-profiles/{novo_perfil.id}/edit?sucesso={quote(f'Perfil #{profile_id} duplicado com sucesso.')}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{profile_id}/delete")
def excluir_perfil_page(profile_id: int, db: Session = Depends(get_db), usuario: User = Depends(get_authenticated_user)):
    sucesso, mensagem = excluir_perfil(db, profile_id, usuario.id)

    if not sucesso:
        return RedirectResponse(
            url=f"/writing-profiles?erro={mensagem}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"/writing-profiles?sucesso={mensagem}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
