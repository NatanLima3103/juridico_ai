from datetime import date, datetime, time
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.writing_profile import WritingProfile
from app.schemas.writing_profile import WritingProfileCreate
from app.services.audit_service import registrar_evento_auditoria, serializar_entidade_para_auditoria


def _parse_date_input(raw_value: str | None) -> date | None:
    valor = (raw_value or "").strip()

    if not valor:
        return None

    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalizar_texto(valor: str | None) -> str:
    return (valor or "").strip()


def obter_ordenacoes_perfis() -> dict[str, str]:
    return {
        "created_desc": "Mais recentes primeiro",
        "created_asc": "Mais antigos primeiro",
        "name_asc": "Nome (A-Z)",
        "name_desc": "Nome (Z-A)",
        "lawyer_asc": "Advogado (A-Z)",
        "lawyer_desc": "Advogado (Z-A)",
    }


def normalizar_filtros_perfis(
    search: str = "",
    profile_name: str = "",
    lawyer_name: str = "",
    office_name: str = "",
    tone: str = "",
    created_from: str = "",
    created_to: str = "",
    sort_by: str = "created_desc",
) -> dict[str, Any]:
    ordenacoes_validas = set(obter_ordenacoes_perfis().keys())

    created_from_date = _parse_date_input(created_from)
    created_to_date = _parse_date_input(created_to)

    return {
        "search": _normalizar_texto(search),
        "profile_name": _normalizar_texto(profile_name),
        "lawyer_name": _normalizar_texto(lawyer_name),
        "office_name": _normalizar_texto(office_name),
        "tone": _normalizar_texto(tone),
        "created_from": created_from_date.isoformat() if created_from_date else "",
        "created_to": created_to_date.isoformat() if created_to_date else "",
        "_created_from_date": created_from_date,
        "_created_to_date": created_to_date,
        "sort_by": sort_by if sort_by in ordenacoes_validas else "created_desc",
    }


def contar_filtros_ativos_perfis(filtros: dict[str, Any] | None) -> int:
    if not filtros:
        return 0

    total = 0

    if filtros.get("search"):
        total += 1
    if filtros.get("profile_name"):
        total += 1
    if filtros.get("lawyer_name"):
        total += 1
    if filtros.get("office_name"):
        total += 1
    if filtros.get("tone"):
        total += 1
    if filtros.get("created_from"):
        total += 1
    if filtros.get("created_to"):
        total += 1
    if filtros.get("sort_by", "created_desc") != "created_desc":
        total += 1

    return total


def obter_tons_disponiveis(db: Session, user_id: int) -> list[str]:
    resultados = (
        db.query(WritingProfile.tone)
        .filter(WritingProfile.user_id == user_id)
        .filter(WritingProfile.deleted_at.is_(None))
        .filter(WritingProfile.tone.isnot(None))
        .order_by(WritingProfile.tone.asc())
        .all()
    )

    tons: list[str] = []
    for (tone,) in resultados:
        tone_limpo = _normalizar_texto(tone)
        if tone_limpo and tone_limpo not in tons:
            tons.append(tone_limpo)

    return tons


def validar_dados_perfil(
    profile_name: str,
    tone: str,
    lawyer_name: str = "",
    office_name: str = "",
    qualification_style: str = "",
    opening_phrase: str = "",
    request_intro: str = "",
    closing_phrase: str = "",
    legal_style_notes: str = "",
    recurring_expressions: str = "",
    tags: str = "",
    is_favorite: bool = False,
    status: str = "",
) -> dict[str, str]:
    profile_name = _normalizar_texto(profile_name)
    tone = _normalizar_texto(tone)
    lawyer_name = _normalizar_texto(lawyer_name)
    office_name = _normalizar_texto(office_name)
    qualification_style = _normalizar_texto(qualification_style)
    opening_phrase = _normalizar_texto(opening_phrase)
    request_intro = _normalizar_texto(request_intro)
    closing_phrase = _normalizar_texto(closing_phrase)
    legal_style_notes = _normalizar_texto(legal_style_notes)
    recurring_expressions = _normalizar_texto(recurring_expressions)
    tags = _normalizar_texto(tags)
    status = _normalizar_texto(status)

    if not profile_name:
        raise ValueError("Informe o nome do perfil.")
    if len(profile_name) < 3:
        raise ValueError("O nome do perfil deve ter pelo menos 3 caracteres.")

    if not tone:
        raise ValueError("Informe o tom da escrita.")
    if len(tone) < 3:
        raise ValueError("O tom da escrita deve ter pelo menos 3 caracteres.")

    return {
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
        "is_favorite": bool(is_favorite),
        "status": status,
    }


def criar_perfil(db: Session, payload: WritingProfileCreate) -> WritingProfile:
    perfil = WritingProfile(
        user_id=payload.user_id,
        profile_name=_normalizar_texto(payload.profile_name),
        lawyer_name=_normalizar_texto(payload.lawyer_name),
        office_name=_normalizar_texto(payload.office_name),
        tone=_normalizar_texto(payload.tone) or "Formal",
        qualification_style=_normalizar_texto(payload.qualification_style),
        opening_phrase=_normalizar_texto(payload.opening_phrase),
        request_intro=_normalizar_texto(payload.request_intro),
        closing_phrase=_normalizar_texto(payload.closing_phrase),
        legal_style_notes=_normalizar_texto(payload.legal_style_notes),
        recurring_expressions=_normalizar_texto(payload.recurring_expressions),
        tags=_normalizar_texto(payload.tags) or None,
        is_favorite=bool(getattr(payload, "is_favorite", False)),
        status=_normalizar_texto(payload.status) or None,
        is_active=bool(getattr(payload, "is_active", False)),
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)

    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=perfil.id,
        action="create",
        entity_version=perfil.version,
        snapshot=serializar_entidade_para_auditoria(perfil),
    )
    db.commit()
    return perfil


def buscar_perfil_por_id(db: Session, profile_id: int, user_id: int) -> WritingProfile | None:
    return (
        db.query(WritingProfile)
        .filter(
            WritingProfile.id == profile_id,
            WritingProfile.user_id == user_id,
            WritingProfile.deleted_at.is_(None),
        )
        .first()
    )


def atualizar_perfil(
    db: Session,
    profile_id: int,
    user_id: int,
    payload: WritingProfileCreate,
) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id, user_id)

    if not perfil:
        return None

    perfil.profile_name = _normalizar_texto(payload.profile_name)
    perfil.lawyer_name = _normalizar_texto(payload.lawyer_name)
    perfil.office_name = _normalizar_texto(payload.office_name)
    perfil.tone = _normalizar_texto(payload.tone) or "Formal"
    perfil.qualification_style = _normalizar_texto(payload.qualification_style)
    perfil.opening_phrase = _normalizar_texto(payload.opening_phrase)
    perfil.request_intro = _normalizar_texto(payload.request_intro)
    perfil.closing_phrase = _normalizar_texto(payload.closing_phrase)
    perfil.legal_style_notes = _normalizar_texto(payload.legal_style_notes)
    perfil.recurring_expressions = _normalizar_texto(payload.recurring_expressions)
    perfil.tags = _normalizar_texto(payload.tags) or None
    perfil.status = _normalizar_texto(payload.status) or None
    perfil.version = int(getattr(perfil, "version", 1) or 1) + 1

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=perfil.id,
        action="update",
        entity_version=perfil.version,
        snapshot=serializar_entidade_para_auditoria(perfil),
    )
    db.commit()
    return perfil


def _gerar_nome_duplicado(db: Session, nome_original: str, user_id: int) -> str:
    nome_base = _normalizar_texto(nome_original) or "Perfil sem nome"
    candidato = f"{nome_base} (cópia)"
    contador = 2

    while db.query(WritingProfile).filter(
        WritingProfile.user_id == user_id,
        WritingProfile.profile_name == candidato,
        WritingProfile.deleted_at.is_(None),
    ).first():
        candidato = f"{nome_base} (cópia {contador})"
        contador += 1

    return candidato


def duplicar_perfil(db: Session, profile_id: int, user_id: int) -> WritingProfile | None:
    perfil_origem = buscar_perfil_por_id(db, profile_id, user_id)

    if not perfil_origem:
        return None

    novo_perfil = WritingProfile(
        user_id=user_id,
        profile_name=_gerar_nome_duplicado(db, perfil_origem.profile_name, user_id),
        lawyer_name=_normalizar_texto(perfil_origem.lawyer_name),
        office_name=_normalizar_texto(perfil_origem.office_name),
        tone=_normalizar_texto(perfil_origem.tone) or "Formal",
        qualification_style=_normalizar_texto(perfil_origem.qualification_style),
        opening_phrase=_normalizar_texto(perfil_origem.opening_phrase),
        request_intro=_normalizar_texto(perfil_origem.request_intro),
        closing_phrase=_normalizar_texto(perfil_origem.closing_phrase),
        legal_style_notes=_normalizar_texto(perfil_origem.legal_style_notes),
        recurring_expressions=_normalizar_texto(perfil_origem.recurring_expressions),
        tags=_normalizar_texto(perfil_origem.tags) or None,
        status=_normalizar_texto(perfil_origem.status) or None,
        is_active=False,
        is_pinned=False,
        is_favorite=False,
    )

    db.add(novo_perfil)
    db.commit()
    db.refresh(novo_perfil)
    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=novo_perfil.id,
        action="duplicate",
        entity_version=novo_perfil.version,
        snapshot=serializar_entidade_para_auditoria(novo_perfil),
    )
    db.commit()
    return novo_perfil


def toggle_fixacao_perfil(db: Session, profile_id: int, user_id: int) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id, user_id)

    if not perfil:
        return None

    perfil.is_pinned = not bool(perfil.is_pinned)
    perfil.version = int(getattr(perfil, "version", 1) or 1) + 1

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=perfil.id,
        action="toggle_pin",
        entity_version=perfil.version,
        snapshot=serializar_entidade_para_auditoria(perfil),
    )
    db.commit()
    return perfil


def toggle_favorito_perfil(db: Session, profile_id: int, user_id: int) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id, user_id)

    if not perfil:
        return None

    perfil.is_favorite = not bool(perfil.is_favorite)
    perfil.version = int(getattr(perfil, "version", 1) or 1) + 1

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=perfil.id,
        action="toggle_favorite",
        entity_version=perfil.version,
        snapshot=serializar_entidade_para_auditoria(perfil),
    )
    db.commit()
    return perfil


def excluir_perfil(db: Session, profile_id: int, user_id: int) -> tuple[bool, str]:
    perfil = buscar_perfil_por_id(db, profile_id, user_id)

    if not perfil:
        return False, "Perfil não encontrado."

    perfil.deleted_at = perfil.deleted_at or datetime.now()
    perfil.updated_at = perfil.deleted_at
    perfil.version = int(getattr(perfil, "version", 1) or 1) + 1

    registrar_evento_auditoria(
        db,
        entity_type="writing_profile",
        entity_id=perfil.id,
        action="delete",
        entity_version=perfil.version,
        snapshot=serializar_entidade_para_auditoria(perfil),
    )
    db.add(perfil)
    db.commit()
    return True, "Perfil excluído com sucesso."


def listar_perfis_filtrados(
    db: Session,
    user_id: int,
    filtros: dict[str, Any] | None = None,
) -> list[WritingProfile]:
    filtros = filtros or {}

    query = db.query(WritingProfile).filter(WritingProfile.user_id == user_id, WritingProfile.deleted_at.is_(None))

    search = _normalizar_texto(filtros.get("search"))
    if search:
        like_term = f"%{search}%"
        query = query.filter(
            or_(
                WritingProfile.profile_name.ilike(like_term),
                WritingProfile.lawyer_name.ilike(like_term),
                WritingProfile.office_name.ilike(like_term),
                WritingProfile.tone.ilike(like_term),
                WritingProfile.qualification_style.ilike(like_term),
                WritingProfile.opening_phrase.ilike(like_term),
                WritingProfile.request_intro.ilike(like_term),
                WritingProfile.closing_phrase.ilike(like_term),
                WritingProfile.legal_style_notes.ilike(like_term),
                WritingProfile.recurring_expressions.ilike(like_term),
                WritingProfile.tags.ilike(like_term),
                WritingProfile.status.ilike(like_term),
            )
        )

    profile_name = _normalizar_texto(filtros.get("profile_name"))
    if profile_name:
        query = query.filter(WritingProfile.profile_name.ilike(f"%{profile_name}%"))

    lawyer_name = _normalizar_texto(filtros.get("lawyer_name"))
    if lawyer_name:
        query = query.filter(WritingProfile.lawyer_name.ilike(f"%{lawyer_name}%"))

    office_name = _normalizar_texto(filtros.get("office_name"))
    if office_name:
        query = query.filter(WritingProfile.office_name.ilike(f"%{office_name}%"))

    tone = _normalizar_texto(filtros.get("tone"))
    if tone:
        query = query.filter(WritingProfile.tone == tone)

    created_from: date | None = filtros.get("_created_from_date")
    if created_from:
        query = query.filter(
            WritingProfile.created_at >= datetime.combine(created_from, time.min)
        )

    created_to: date | None = filtros.get("_created_to_date")
    if created_to:
        query = query.filter(
            WritingProfile.created_at <= datetime.combine(created_to, time.max)
        )

    sort_by = filtros.get("sort_by", "created_desc")

    if sort_by == "created_asc":
        query = query.order_by(WritingProfile.created_at.asc(), WritingProfile.id.asc())
    elif sort_by == "name_asc":
        query = query.order_by(WritingProfile.profile_name.asc(), WritingProfile.id.asc())
    elif sort_by == "name_desc":
        query = query.order_by(WritingProfile.profile_name.desc(), WritingProfile.id.desc())
    elif sort_by == "lawyer_asc":
        query = query.order_by(WritingProfile.lawyer_name.asc(), WritingProfile.id.asc())
    elif sort_by == "lawyer_desc":
        query = query.order_by(WritingProfile.lawyer_name.desc(), WritingProfile.id.desc())
    else:
        query = query.order_by(
            WritingProfile.is_pinned.desc(),
            WritingProfile.is_favorite.desc(),
            WritingProfile.created_at.desc(),
            WritingProfile.id.desc(),
        )

    return query.all()


def listar_perfis_escrita(db: Session, user_id: int) -> list[WritingProfile]:
    return (
        db.query(WritingProfile)
        .filter(WritingProfile.user_id == user_id, WritingProfile.deleted_at.is_(None))
        .order_by(WritingProfile.is_pinned.desc(), WritingProfile.profile_name.asc())
        .all()
    )


def listar_perfis(db: Session, user_id: int) -> list[WritingProfile]:
    return listar_perfis_escrita(db, user_id)


def montar_resumo_perfil(perfil: WritingProfile) -> dict[str, Any]:
    return {
        "id": perfil.id,
        "profile_name": _normalizar_texto(perfil.profile_name) or "Sem nome",
        "tone": _normalizar_texto(perfil.tone) or "Formal",
        "lawyer_name": _normalizar_texto(perfil.lawyer_name) or "Não informado",
        "office_name": _normalizar_texto(perfil.office_name) or "Não informado",
        "qualification_style": _normalizar_texto(perfil.qualification_style) or "Não informado",
        "opening_phrase": _normalizar_texto(perfil.opening_phrase) or "Não informada",
        "request_intro": _normalizar_texto(perfil.request_intro) or "Não informada",
        "closing_phrase": _normalizar_texto(perfil.closing_phrase) or "Não informada",
        "legal_style_notes": _normalizar_texto(perfil.legal_style_notes) or "Não informado",
        "recurring_expressions": _normalizar_texto(perfil.recurring_expressions) or "Não informado",
        "tags": _normalizar_texto(perfil.tags),
        "status": _normalizar_texto(perfil.status),
        "is_active": bool(perfil.is_active),
        "is_pinned": bool(perfil.is_pinned),
        "is_favorite": bool(perfil.is_favorite),
        "created_at": getattr(perfil, "created_at", None),
    }
