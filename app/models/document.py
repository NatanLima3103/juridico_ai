from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.generation import generation_documents


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String(255), nullable=False, index=True)
    saved_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False, index=True)
    extracted_text = Column(Text, nullable=False)

    tags = Column(Text, nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=False)
    status = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    generations = relationship(
        "Generation",
        secondary=generation_documents,
        back_populates="documents",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} original_filename='{self.original_filename}'>"