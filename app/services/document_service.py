from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentCreate


def criar_documento(db: Session, document_data: DocumentCreate) -> Document:
    documento = Document(
        original_filename=document_data.original_filename,
        saved_filename=document_data.saved_filename,
        file_path=document_data.file_path,
        file_type=document_data.file_type,
        extracted_text=document_data.extracted_text,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)
    return documento


def listar_documentos(db: Session) -> list[Document]:
    return db.query(Document).order_by(Document.created_at.desc()).all()


def buscar_documento_por_id(db: Session, document_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def montar_dados_documento(
    original_filename: str,
    saved_path: Path,
    extracted_text: str,
) -> DocumentCreate:
    return DocumentCreate(
        original_filename=original_filename,
        saved_filename=saved_path.name,
        file_path=str(saved_path),
        file_type=saved_path.suffix.lower(),
        extracted_text=extracted_text,
    )