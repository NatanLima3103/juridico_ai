from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def agora_brasil():
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        except ZoneInfoNotFoundError:
            pass
        except Exception:
            pass

    return datetime.now()


class WritingProfile(Base):
    __tablename__ = "writing_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_name = Column(String(150), nullable=False, index=True)
    lawyer_name = Column(String(150), nullable=True)
    office_name = Column(String(200), nullable=True)

    tone = Column(String(100), nullable=False, default="Formal")
    qualification_style = Column(
        Text,
        nullable=True,
        default="já qualificado(a) nos autos ou a ser devidamente qualificado(a)",
    )
    opening_phrase = Column(
        Text,
        nullable=True,
        default="vem, com o devido respeito, à presença de Vossa Excelência, apresentar a presente:",
    )
    closing_phrase = Column(
        Text,
        nullable=True,
        default="Termos em que,\nPede deferimento.",
    )
    request_intro = Column(
        Text,
        nullable=True,
        default="Diante do exposto, requer:",
    )
    legal_style_notes = Column(
        Text,
        nullable=True,
        default="Utilizar linguagem jurídica formal, objetiva e técnica.",
    )
    recurring_expressions = Column(
        Text,
        nullable=True,
        default="data venia; conforme entendimento jurisprudencial; nos termos da legislação aplicável",
    )

    is_active = Column(Boolean, default=False, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)

    tags = Column(Text, nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=False)
    status = Column(String(100), nullable=True)
    version = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, default=agora_brasil, nullable=False)
    updated_at = Column(DateTime, default=agora_brasil, onupdate=agora_brasil, nullable=False)

    generations = relationship(
        "Generation",
        back_populates="writing_profile",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<WritingProfile id={self.id} profile_name='{self.profile_name}'>"
