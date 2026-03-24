from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


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

    writing_profile_id = Column(
        Integer,
        ForeignKey("writing_profiles.id"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    writing_profile = relationship("WritingProfile")