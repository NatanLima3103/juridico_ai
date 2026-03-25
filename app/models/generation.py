from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def agora_brasil():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(String(255), nullable=False)
    document_type = Column(String(255), nullable=False)
    case_subject = Column(String(255), nullable=False)
    facts = Column(Text, nullable=False)
    requests = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=True)
    context_used = Column(Text, nullable=False)
    generated_text = Column(Text, nullable=False)

    source_document_ids = Column(Text, nullable=True)

    writing_profile_id = Column(
        Integer,
        ForeignKey("writing_profiles.id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=agora_brasil,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=agora_brasil,
        nullable=False,
    )

    writing_profile = relationship("WritingProfile")