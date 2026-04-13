from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text
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


generation_documents = Table(
    "generation_documents",
    Base.metadata,
    Column(
        "generation_id",
        Integer,
        ForeignKey("generations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "document_id",
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Generation(Base):
    __tablename__ = "generations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    client_name = Column(Text, nullable=False)
    document_type = Column(Text, nullable=False, index=True)
    case_subject = Column(Text, nullable=False, index=True)
    facts = Column(Text, nullable=False)
    requests = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=True)
    context_used = Column(Text, nullable=False)
    generated_text = Column(Text, nullable=False)
    generation_strategy = Column(String(50), nullable=False, default="rule_based")
    llm_provider = Column(String(50), nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_response_id = Column(String(100), nullable=True)
    llm_error = Column(Text, nullable=True)

    # Mantido temporariamente como texto para compatibilidade com bancos já existentes.
    # A relação oficial com documentos agora é feita por generation_documents.
    source_document_ids = Column(Text, nullable=True)

    writing_profile_id = Column(
        Integer,
        ForeignKey("writing_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    writing_profile = relationship(
        "WritingProfile",
        back_populates="generations",
        passive_deletes=True,
    )

    documents = relationship(
        "Document",
        secondary=generation_documents,
        back_populates="generations",
        passive_deletes=True,
    )
    user = relationship("User", passive_deletes=True)

    tags = Column(Text, nullable=True)
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_favorite = Column(Boolean, default=False, nullable=False)
    status = Column(String(100), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=agora_brasil, nullable=False, index=True)
    updated_at = Column(DateTime, default=agora_brasil, onupdate=agora_brasil, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)

    @property
    def writing_profile_name(self):
        if self.writing_profile:
            return self.writing_profile.profile_name
        return "Sem perfil"

    @property
    def document_ids(self) -> list[int]:
        if self.documents:
            return [document.id for document in self.documents if getattr(document, "id", None) is not None]

        if not self.source_document_ids:
            return []

        ids: list[int] = []
        for parte in self.source_document_ids.split(","):
            valor = (parte or "").strip()
            if not valor:
                continue
            try:
                numero = int(valor)
            except ValueError:
                continue
            if numero not in ids:
                ids.append(numero)

        return ids

    def __repr__(self) -> str:
        return f"<Generation id={self.id} client_name='{self.client_name}'>"
