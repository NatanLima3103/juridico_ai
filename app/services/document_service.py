from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import Document
from app.schemas.document import DocumentCreate


ORDENACOES_DOCUMENTOS = {
    "recentes": "Mais recentes primeiro",
    "antigos": "Mais antigos primeiro",
    "nome_az": "Nome (A-Z)",
    "nome_za": "Nome (Z-A)",
    "tipo_az": "Tipo (A-Z)",
}


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


def listar_documentos_por_ids(db: Session, document_ids: list[int]) -> list[Document]:
    if not document_ids:
        return []

    documentos = (
        db.query(Document)
        .filter(Document.id.in_(document_ids))
        .order_by(Document.created_at.desc())
        .all()
    )

    documentos_por_id = {documento.id: documento for documento in documentos}

    documentos_ordenados = [
        documentos_por_id[document_id]
        for document_id in document_ids
        if document_id in documentos_por_id
    ]

    return documentos_ordenados


def buscar_documento_por_id(db: Session, document_id: int) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def excluir_documento(db: Session, documento: Document) -> None:
    caminho = obter_path_documento(documento)

    if caminho.exists():
        caminho.unlink()

    db.delete(documento)
    db.commit()


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
        extracted_text=normalizar_texto_extraido(extracted_text),
    )


def obter_path_documento(documento: Document) -> Path:
    return Path(documento.file_path)


def documento_existe(documento: Document) -> bool:
    return obter_path_documento(documento).exists()


def obter_tamanho_arquivo(documento: Document) -> int | None:
    caminho = obter_path_documento(documento)

    if not caminho.exists():
        return None

    return caminho.stat().st_size


def formatar_tamanho_arquivo(size_in_bytes: int | None) -> str:
    if size_in_bytes is None:
        return "Arquivo não localizado"

    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"

    if size_in_bytes < 1024 * 1024:
        return f"{size_in_bytes / 1024:.2f} KB"

    return f"{size_in_bytes / (1024 * 1024):.2f} MB"


def normalizar_texto_extraido(texto: str) -> str:
    texto = (texto or "").replace("\x00", "").strip()

    if not texto:
        return "Nenhum texto foi encontrado no arquivo."

    return texto


def resumir_texto_extraido(texto: str, limite: int = 300) -> str:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return "Nenhum texto foi extraído."

    if len(texto_limpo) <= limite:
        return texto_limpo

    return texto_limpo[:limite].rstrip() + "..."


def contar_caracteres_texto(texto: str) -> int:
    return len(texto or "")


def contar_palavras_texto(texto: str) -> int:
    texto_limpo = " ".join((texto or "").split())

    if not texto_limpo:
        return 0

    return len(texto_limpo.split())