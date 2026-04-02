from sqlalchemy.orm import Session

from app.models.writing_profile import WritingProfile


def criar_perfil_escrita(
    db: Session,
    profile_name: str,
    lawyer_name: str,
    office_name: str,
    qualification_style: str,
    opening_phrase: str,
    request_intro: str,
    closing_phrase: str,
    tone: str,
    legal_style_notes: str,
    recurring_expressions: str,
):
    perfil = WritingProfile(
        profile_name=profile_name.strip(),
        lawyer_name=(lawyer_name or "").strip(),
        office_name=(office_name or "").strip(),
        qualification_style=(qualification_style or "").strip(),
        opening_phrase=(opening_phrase or "").strip(),
        request_intro=(request_intro or "").strip(),
        closing_phrase=(closing_phrase or "").strip(),
        tone=(tone or "").strip(),
        legal_style_notes=(legal_style_notes or "").strip(),
        recurring_expressions=(recurring_expressions or "").strip(),
    )

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def listar_perfis_escrita(db: Session):
    return db.query(WritingProfile).order_by(WritingProfile.profile_name.asc()).all()


def buscar_perfil_por_id(db: Session, profile_id: int):
    return db.query(WritingProfile).filter(WritingProfile.id == profile_id).first()


def atualizar_perfil_escrita(
    db: Session,
    perfil: WritingProfile,
    profile_name: str,
    lawyer_name: str,
    office_name: str,
    qualification_style: str,
    opening_phrase: str,
    request_intro: str,
    closing_phrase: str,
    tone: str,
    legal_style_notes: str,
    recurring_expressions: str,
):
    perfil.profile_name = profile_name.strip()
    perfil.lawyer_name = (lawyer_name or "").strip()
    perfil.office_name = (office_name or "").strip()
    perfil.qualification_style = (qualification_style or "").strip()
    perfil.opening_phrase = (opening_phrase or "").strip()
    perfil.request_intro = (request_intro or "").strip()
    perfil.closing_phrase = (closing_phrase or "").strip()
    perfil.tone = (tone or "").strip()
    perfil.legal_style_notes = (legal_style_notes or "").strip()
    perfil.recurring_expressions = (recurring_expressions or "").strip()

    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def excluir_perfil_escrita(db: Session, perfil: WritingProfile):
    db.delete(perfil)
    db.commit()