from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class WritingProfile(Base):
    __tablename__ = "writing_profiles"

    id = Column(Integer, primary_key=True, index=True)
    profile_name = Column(String(150), nullable=False)
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

    created_at = Column(DateTime(timezone=True), server_default=func.now())