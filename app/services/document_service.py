from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import UPLOAD_PATH
from app.models.document import Document, agora_brasil
from app.schemas.document import DocumentCreate
from app.services.audit_service import registrar_evento_auditoria, serializar_entidade_para_auditoria


ORDENACOES_DOCUMENTOS = {
    "recentes": "Mais recentes primeiro",
    "antigos": "Mais antigos primeiro",
    "nome_az": "Nome (A-Z)",
    "nome_za": "Nome (Z-A)",
    "tipo_az": "Tipo (A-Z)",
}


def _normalizar_texto(valor: str | None) -> str:
    return (valor or "").strip()


def criar_documento(db: Session, document_data: DocumentCreate) -> Document:
    documento = Document(
        original_filename=document_data.original_filename,
        saved_filename=document_data.saved_filename,
        file_path=document_data.file_path,
        file_type=document_data.file_type,
        extracted_text=document_data.extracted_text,
        user_id=document_data.user_id,
        tags=_normalizar_texto(document_data.tags) or None,
        is_favorite=bool(document_data.is_favorite),
        status=_normalizar_texto(document_data.status) or None,
    )
    db.add(documento)
    db.commit()
    db.refresh(documento)
    registrar_evento_auditoria(
        db,
        entity_type="document",
        entity_id=documento.id,
        action="create",
        entity_version=documento.version,
        snapshot=serializar_entidade_para_auditoria(documento),
    )
    db.commit()
    return documento


def listar_documentos(db: Session, user_id: int) -> list[Document]:
    return (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.deleted_at.is_(None))
        .order_by(Document.is_favorite.desc(), Document.created_at.desc(), Document.id.desc())
        .all()
    )


def listar_documentos_por_ids(db: Session, document_ids: list[int], user_id: int) -> list[Document]:
    ids_unicos = []
    for document_id in document_ids:
        if document_id not in ids_unicos:
            ids_unicos.append(document_id)

    if not ids_unicos:
        return []

    documentos = (
        db.query(Document)
        .filter(Document.user_id == user_id, Document.id.in_(ids_unicos), Document.deleted_at.is_(None))
        .order_by(Document.created_at.desc())
        .all()
    )

    documentos_por_id = {documento.id: documento for documento in documentos}

    documentos_ordenados = [
        documentos_por_id[document_id]
        for document_id in ids_unicos
        if document_id in documentos_por_id
    ]

    return documentos_ordenados


def buscar_documento_por_id(db: Session, document_id: int, user_id: int) -> Document | None:
    return (
        db.query(Document)
        .filter(Document.id == document_id, Document.user_id == user_id, Document.deleted_at.is_(None))
        .first()
    )


def atualizar_metadados_documento(
    db: Session,
    documento: Document,
    *,
    tags: str | None = None,
    status: str | None = None,
) -> Document:
    documento.tags = _normalizar_texto(tags) or None
    documento.status = _normalizar_texto(status) or None
    documento.version = int(getattr(documento, "version", 1) or 1) + 1

    db.add(documento)
    db.commit()
    db.refresh(documento)
    registrar_evento_auditoria(
        db,
        entity_type="document",
        entity_id=documento.id,
        action="update_metadata",
        entity_version=documento.version,
        snapshot=serializar_entidade_para_auditoria(documento),
    )
    db.commit()
    return documento


def toggle_favorito_documento(db: Session, documento: Document) -> Document:
    documento.is_favorite = not bool(documento.is_favorite)
    documento.version = int(getattr(documento, "version", 1) or 1) + 1

    db.add(documento)
    db.commit()
    db.refresh(documento)
    registrar_evento_auditoria(
        db,
        entity_type="document",
        entity_id=documento.id,
        action="toggle_favorite",
        entity_version=documento.version,
        snapshot=serializar_entidade_para_auditoria(documento),
    )
    db.commit()
    return documento


def excluir_documento(db: Session, documento: Document) -> None:
    documento.deleted_at = documento.deleted_at or agora_brasil()
    documento.updated_at = documento.deleted_at
    documento.version = int(getattr(documento, "version", 1) or 1) + 1
    snapshot = serializar_entidade_para_auditoria(documento)

    registrar_evento_auditoria(
        db,
        entity_type="document",
        entity_id=documento.id,
        action="delete",
        entity_version=documento.version,
        snapshot=snapshot,
    )
    db.add(documento)
    db.commit()


def montar_dados_documento(
    original_filename: str,
    saved_path: Path,
    extracted_text: str,
    user_id: int,
) -> DocumentCreate:
    return DocumentCreate(
        original_filename=original_filename,
        saved_filename=saved_path.name,
        file_path=str(saved_path),
        file_type=saved_path.suffix.lower(),
        extracted_text=normalizar_texto_extraido(extracted_text),
        user_id=user_id,
        tags=None,
        is_favorite=False,
        status=None,
    )


def obter_path_documento(documento: Document) -> Path:
    return proteger_path_documento(Path(documento.file_path or ""))


def proteger_path_documento(caminho: Path) -> Path:
    caminho_resolvido = caminho.resolve(strict=False)
    upload_path_resolvido = UPLOAD_PATH.resolve(strict=False)

    try:
        caminho_resolvido.relative_to(upload_path_resolvido)
    except ValueError as exc:
        raise ValueError("Caminho de arquivo fora do armazenamento permitido.") from exc

    return caminho_resolvido


def documento_existe(documento: Document) -> bool:
    try:
        caminho = obter_path_documento(documento)
    except ValueError:
        return False

    return caminho.is_file()


def obter_tamanho_arquivo(documento: Document) -> int | None:
    try:
        caminho = obter_path_documento(documento)
    except ValueError:
        return None

    if not caminho.is_file():
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
