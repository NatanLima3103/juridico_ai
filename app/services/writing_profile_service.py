from sqlalchemy.orm import Session

from app.models.writing_profile import WritingProfile
from app.schemas.writing_profile import WritingProfileCreate


def normalizar_campo(texto: str | None) -> str | None:
    if texto is None:
        return None

    texto = texto.strip()
    return texto or None


def desativar_todos_os_perfis(db: Session) -> None:
    perfis = db.query(WritingProfile).all()

    for perfil in perfis:
        perfil.is_active = False

    db.commit()


def criar_writing_profile(db: Session, profile_data: WritingProfileCreate) -> WritingProfile:
    if profile_data.is_active:
        desativar_todos_os_perfis(db)

    perfil = WritingProfile(
        profile_name=profile_data.profile_name.strip(),
        lawyer_name=normalizar_campo(profile_data.lawyer_name),
        office_name=normalizar_campo(profile_data.office_name),
        tone=profile_data.tone.strip(),
        qualification_style=normalizar_campo(profile_data.qualification_style),
        opening_phrase=normalizar_campo(profile_data.opening_phrase),
        closing_phrase=normalizar_campo(profile_data.closing_phrase),
        request_intro=normalizar_campo(profile_data.request_intro),
        legal_style_notes=normalizar_campo(profile_data.legal_style_notes),
        recurring_expressions=normalizar_campo(profile_data.recurring_expressions),
        is_active=profile_data.is_active,
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)

    return perfil


def listar_writing_profiles(db: Session) -> list[WritingProfile]:
    return db.query(WritingProfile).order_by(WritingProfile.created_at.desc()).all()


def buscar_writing_profile_por_id(db: Session, profile_id: int) -> WritingProfile | None:
    return db.query(WritingProfile).filter(WritingProfile.id == profile_id).first()


def buscar_perfil_ativo(db: Session) -> WritingProfile | None:
    return db.query(WritingProfile).filter(WritingProfile.is_active == True).first()


def ativar_writing_profile(db: Session, profile_id: int) -> WritingProfile | None:
    perfil = buscar_writing_profile_por_id(db, profile_id)

    if not perfil:
        return None

    desativar_todos_os_perfis(db)

    perfil.is_active = True
    db.commit()
    db.refresh(perfil)

    return perfil