from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text
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


class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    client_name = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False)
    case_subject = Column(Text, nullable=False)
    facts = Column(Text, nullable=False)
    requests = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=True)
    context_used = Column(Text, nullable=False)
    generated_text = Column(Text, nullable=False)
    source_document_ids = Column(Text, nullable=True)

    writing_profile_id = Column(Integer, ForeignKey("writing_profiles.id"), nullable=True)
    writing_profile = relationship("WritingProfile", back_populates="generations")

    is_pinned = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=agora_brasil, nullable=False)
    updated_at = Column(DateTime, default=agora_brasil, onupdate=agora_brasil, nullable=False)

    @property
    def writing_profile_name(self):
        if self.writing_profile:
            return self.writing_profile.profile_name
        return "Sem perfil"