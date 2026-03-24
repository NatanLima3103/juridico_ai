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


def buscar_perfil_ativo(db: Session) -> WritingProfile | None:
    return (
        db.query(WritingProfile)
        .filter(WritingProfile.is_active.is_(True))
        .order_by(WritingProfile.created_at.desc())
        .first()
    )


def desativar_todos_perfis(db: Session) -> None:
    perfis_ativos = (
        db.query(WritingProfile)
        .filter(WritingProfile.is_active.is_(True))
        .all()
    )

    for perfil in perfis_ativos:
        perfil.is_active = False

    db.commit()


def criar_perfil(db: Session, profile_data) -> WritingProfile:
    perfil_ativo = buscar_perfil_ativo(db)

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
        is_active=False if perfil_ativo else True,
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def ativar_perfil(db: Session, profile_id: int) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id)

    if not perfil:
        return None

    desativar_todos_perfis(db)
    perfil.is_active = True
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

    perfil_era_ativo = perfil.is_active

    db.delete(perfil)
    db.commit()

    if perfil_era_ativo:
        proximo_perfil = buscar_perfil_ativo(db)

        if not proximo_perfil:
            perfil_mais_recente = (
                db.query(WritingProfile)
                .order_by(WritingProfile.created_at.desc())
                .first()
            )

            if perfil_mais_recente:
                perfil_mais_recente.is_active = True
                db.commit()

    return True, "Perfil excluído com sucesso."


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
        "is_active": perfil.is_active,
        "created_at": perfil.created_at,
    }