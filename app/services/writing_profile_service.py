from sqlalchemy.orm import Session

from app.models.writing_profile import WritingProfile
from app.schemas.writing_profile import WritingProfileCreate


def normalizar_campo(texto: str | None) -> str | None:
    if texto is None:
        return None

    texto = " ".join(texto.strip().split())
    return texto or None


def validar_dados_perfil(
    profile_name: str,
    tone: str,
    lawyer_name: str | None = None,
    office_name: str | None = None,
    qualification_style: str | None = None,
    opening_phrase: str | None = None,
    request_intro: str | None = None,
    closing_phrase: str | None = None,
    legal_style_notes: str | None = None,
    recurring_expressions: str | None = None,
) -> dict:
    dados = {
        "profile_name": normalizar_campo(profile_name),
        "tone": normalizar_campo(tone),
        "lawyer_name": normalizar_campo(lawyer_name),
        "office_name": normalizar_campo(office_name),
        "qualification_style": normalizar_campo(qualification_style),
        "opening_phrase": normalizar_campo(opening_phrase),
        "request_intro": normalizar_campo(request_intro),
        "closing_phrase": normalizar_campo(closing_phrase),
        "legal_style_notes": normalizar_campo(legal_style_notes),
        "recurring_expressions": normalizar_campo(recurring_expressions),
    }

    if not dados["profile_name"]:
        raise ValueError("Informe o nome do perfil.")

    if len(dados["profile_name"]) < 3:
        raise ValueError("O nome do perfil deve ter pelo menos 3 caracteres.")

    if not dados["tone"]:
        raise ValueError("Informe o tom de escrita do perfil.")

    if len(dados["tone"]) < 3:
        raise ValueError("O tom deve ter pelo menos 3 caracteres.")

    return dados


def criar_perfil(db: Session, profile_data: WritingProfileCreate) -> WritingProfile:
    perfil = WritingProfile(
        profile_name=profile_data.profile_name,
        tone=profile_data.tone,
        lawyer_name=profile_data.lawyer_name,
        office_name=profile_data.office_name,
        qualification_style=profile_data.qualification_style,
        opening_phrase=profile_data.opening_phrase,
        request_intro=profile_data.request_intro,
        closing_phrase=profile_data.closing_phrase,
        legal_style_notes=profile_data.legal_style_notes,
        recurring_expressions=profile_data.recurring_expressions,
        is_active=False,
    )
    db.add(perfil)
    db.commit()
    db.refresh(perfil)
    return perfil


def listar_perfis(db: Session) -> list[WritingProfile]:
    return db.query(WritingProfile).order_by(WritingProfile.created_at.desc()).all()


def buscar_perfil_por_id(db: Session, profile_id: int) -> WritingProfile | None:
    return db.query(WritingProfile).filter(WritingProfile.id == profile_id).first()


def buscar_perfil_ativo(db: Session) -> WritingProfile | None:
    return (
        db.query(WritingProfile)
        .filter(WritingProfile.is_active == True)
        .first()
    )


def ativar_perfil(db: Session, profile_id: int) -> WritingProfile | None:
    perfil = buscar_perfil_por_id(db, profile_id)

    if not perfil:
        return None

    db.query(WritingProfile).update({WritingProfile.is_active: False})
    perfil.is_active = True
    db.commit()
    db.refresh(perfil)

    return perfil


def resumir_texto(texto: str | None, limite: int = 120) -> str:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return "Não informado."

    if len(texto_limpo) <= limite:
        return texto_limpo

    return texto_limpo[:limite].rstrip() + "..."


def montar_resumo_perfil(perfil: WritingProfile) -> dict:
    return {
        "id": perfil.id,
        "profile_name": perfil.profile_name,
        "tone": perfil.tone,
        "lawyer_name": perfil.lawyer_name or "-",
        "office_name": perfil.office_name or "-",
        "qualification_style_preview": resumir_texto(perfil.qualification_style),
        "opening_phrase_preview": resumir_texto(perfil.opening_phrase),
        "request_intro_preview": resumir_texto(perfil.request_intro),
        "closing_phrase_preview": resumir_texto(perfil.closing_phrase),
        "legal_style_notes_preview": resumir_texto(perfil.legal_style_notes),
        "recurring_expressions_preview": resumir_texto(perfil.recurring_expressions),
        "is_active": perfil.is_active,
        "created_at": perfil.created_at,
    }