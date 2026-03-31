from datetime import datetime, time

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.generation import Generation
from app.models.writing_profile import WritingProfile


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
) -> dict:
    profile_name = (profile_name or "").strip()
    tone = (tone or "").strip()
    lawyer_name = (lawyer_name or "").strip()
    office_name = (office_name or "").strip()
    qualification_style = (qualification_style or "").strip()
    opening_phrase = (opening_phrase or "").strip()
    request_intro = (request_intro or "").strip()
    closing_phrase = (closing_phrase or "").strip()
    legal_style_notes = (legal_style_notes or "").strip()
    recurring_expressions = (recurring_expressions or "").strip()

    if not profile_name:
        raise ValueError("Informe o nome do perfil.")

    if len(profile_name) < 3:
        raise ValueError("O nome do perfil deve ter pelo menos 3 caracteres.")

    if not tone:
        raise ValueError("Informe o tom da escrita.")

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
    }


def listar_perfis(db: Session) -> list[WritingProfile]:
    return db.query(WritingProfile).order_by(WritingProfile.created_at.desc()).all()


def buscar_perfil_por_id(db: Session, profile_id: int) -> WritingProfile | None:
    return db.query(WritingProfile).filter(WritingProfile.id == profile_id).first()


def criar_perfil(db: Session, profile_data) -> WritingProfile:
    perfil = WritingProfile(
        profile_name=profile_data.profile_name,
        lawyer_name=profile_data.lawyer_name,
        office_name=profile_data.office_name,
        tone=profile_data.tone,
        qualification_style=profile_data.qualification_style,
        opening_phrase=profile_data.opening_phrase,
        closing_phrase=profile_data.closing_phrase,
        request_intro=profile_data.request_intro,
        legal_style_notes=profile_data.legal_style_notes,
        recurring_expressions=profile_data.recurring_expressions,
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def atualizar_perfil(db: Session, profile_id: int, profile_data) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id)

    if not perfil:
        return None

    perfil.profile_name = profile_data.profile_name
    perfil.lawyer_name = profile_data.lawyer_name
    perfil.office_name = profile_data.office_name
    perfil.tone = profile_data.tone
    perfil.qualification_style = profile_data.qualification_style
    perfil.opening_phrase = profile_data.opening_phrase
    perfil.closing_phrase = profile_data.closing_phrase
    perfil.request_intro = profile_data.request_intro
    perfil.legal_style_notes = profile_data.legal_style_notes
    perfil.recurring_expressions = profile_data.recurring_expressions

    db.commit()
    db.refresh(perfil)
    return perfil


def perfil_possui_geracoes(db: Session, profile_id: int) -> bool:
    quantidade = (
        db.query(Generation)
        .filter(Generation.writing_profile_id == profile_id)
        .count()
    )
    return quantidade > 0


def excluir_perfil(db: Session, profile_id: int) -> tuple[bool, str]:
    perfil = buscar_perfil_por_id(db, profile_id)

    if not perfil:
        return False, "Perfil de escrita não encontrado."

    if perfil_possui_geracoes(db, profile_id):
        return (
            False,
            "Este perfil não pode ser excluído porque já está vinculado a uma ou mais gerações.",
        )

    db.delete(perfil)
    db.commit()

    return True, "Perfil excluído com sucesso."


def obter_tons_disponiveis(db: Session) -> list[str]:
    resultados = (
        db.query(WritingProfile.tone)
        .filter(WritingProfile.tone.isnot(None))
        .filter(WritingProfile.tone != "")
        .distinct()
        .order_by(WritingProfile.tone.asc())
        .all()
    )

    return [tone for (tone,) in resultados if tone]


def obter_ordenacoes_perfis() -> dict[str, str]:
    return {
        "created_desc": "Mais recentes primeiro",
        "created_asc": "Mais antigos primeiro",
        "profile_name_asc": "Nome do perfil (A-Z)",
        "profile_name_desc": "Nome do perfil (Z-A)",
        "lawyer_name_asc": "Advogado (A-Z)",
        "office_name_asc": "Escritório (A-Z)",
        "tone_asc": "Tom da escrita (A-Z)",
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
) -> dict:
    filtros = {
        "search": (search or "").strip(),
        "profile_name": (profile_name or "").strip(),
        "lawyer_name": (lawyer_name or "").strip(),
        "office_name": (office_name or "").strip(),
        "tone": (tone or "").strip(),
        "created_from": (created_from or "").strip(),
        "created_to": (created_to or "").strip(),
        "sort_by": (sort_by or "created_desc").strip(),
    }

    ordenacoes_validas = obter_ordenacoes_perfis().keys()
    if filtros["sort_by"] not in ordenacoes_validas:
        filtros["sort_by"] = "created_desc"

    return filtros


def contar_filtros_ativos_perfis(filtros: dict) -> int:
    total = 0

    for chave in [
        "search",
        "profile_name",
        "lawyer_name",
        "office_name",
        "tone",
        "created_from",
        "created_to",
    ]:
        if filtros.get(chave):
            total += 1

    if filtros.get("sort_by") and filtros["sort_by"] != "created_desc":
        total += 1

    return total


def listar_perfis_filtrados(db: Session, filtros: dict) -> list[WritingProfile]:
    query = db.query(WritingProfile)

    if filtros["search"]:
        termo = f"%{filtros['search']}%"
        query = query.filter(
            or_(
                WritingProfile.profile_name.ilike(termo),
                WritingProfile.lawyer_name.ilike(termo),
                WritingProfile.office_name.ilike(termo),
                WritingProfile.tone.ilike(termo),
                WritingProfile.qualification_style.ilike(termo),
                WritingProfile.opening_phrase.ilike(termo),
                WritingProfile.request_intro.ilike(termo),
                WritingProfile.closing_phrase.ilike(termo),
                WritingProfile.legal_style_notes.ilike(termo),
                WritingProfile.recurring_expressions.ilike(termo),
            )
        )

    if filtros["profile_name"]:
        query = query.filter(WritingProfile.profile_name.ilike(f"%{filtros['profile_name']}%"))

    if filtros["lawyer_name"]:
        query = query.filter(WritingProfile.lawyer_name.ilike(f"%{filtros['lawyer_name']}%"))

    if filtros["office_name"]:
        query = query.filter(WritingProfile.office_name.ilike(f"%{filtros['office_name']}%"))

    if filtros["tone"]:
        query = query.filter(WritingProfile.tone == filtros["tone"])

    if filtros["created_from"]:
        try:
            data_inicial = datetime.strptime(filtros["created_from"], "%Y-%m-%d")
            query = query.filter(WritingProfile.created_at >= data_inicial)
        except ValueError:
            pass

    if filtros["created_to"]:
        try:
            data_final = datetime.strptime(filtros["created_to"], "%Y-%m-%d")
            data_final = datetime.combine(data_final.date(), time(23, 59, 59))
            query = query.filter(WritingProfile.created_at <= data_final)
        except ValueError:
            pass

    sort_by = filtros["sort_by"]

    if sort_by == "created_asc":
        query = query.order_by(WritingProfile.created_at.asc())
    elif sort_by == "profile_name_asc":
        query = query.order_by(WritingProfile.profile_name.asc(), WritingProfile.created_at.desc())
    elif sort_by == "profile_name_desc":
        query = query.order_by(WritingProfile.profile_name.desc(), WritingProfile.created_at.desc())
    elif sort_by == "lawyer_name_asc":
        query = query.order_by(WritingProfile.lawyer_name.asc(), WritingProfile.profile_name.asc())
    elif sort_by == "office_name_asc":
        query = query.order_by(WritingProfile.office_name.asc(), WritingProfile.profile_name.asc())
    elif sort_by == "tone_asc":
        query = query.order_by(WritingProfile.tone.asc(), WritingProfile.profile_name.asc())
    else:
        query = query.order_by(WritingProfile.created_at.desc())

    return query.all()


def montar_resumo_perfil(perfil: WritingProfile) -> dict:
    return {
        "id": perfil.id,
        "profile_name": perfil.profile_name,
        "lawyer_name": perfil.lawyer_name or "Não informado",
        "office_name": perfil.office_name or "Não informado",
        "tone": perfil.tone or "Formal",
        "qualification_style": perfil.qualification_style or "Não informado",
        "opening_phrase": perfil.opening_phrase or "Não informada",
        "request_intro": perfil.request_intro or "Não informada",
        "closing_phrase": perfil.closing_phrase or "Não informada",
        "legal_style_notes": perfil.legal_style_notes or "Não informadas",
        "recurring_expressions": perfil.recurring_expressions or "Não informadas",
        "created_at": perfil.created_at,
    }