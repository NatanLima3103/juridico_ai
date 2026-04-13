import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document, agora_brasil
from app.models.generation import Generation
from app.models.user import User
from app.models.writing_profile import WritingProfile
from app.services.audit_service import registrar_acao_usuario
from app.services.document_service import proteger_path_documento


LGPD_PLACEHOLDER = "[removido por solicitacao LGPD]"


CATALOGO_DADOS_LGPD: list[dict[str, Any]] = [
    {
        "entidade": "users",
        "dados": ["nome", "email", "senha criptografada", "plano", "status da conta"],
        "base_operacional": "execucao do cadastro e controle de acesso",
        "retencao": "ate encerramento da conta ou anonimizacao",
    },
    {
        "entidade": "documents",
        "dados": ["nome do arquivo", "arquivo enviado", "texto extraido", "tags", "status"],
        "base_operacional": "execucao do servico de organizacao e geracao de minutas",
        "retencao": "quarentena apos exclusao e limpeza pela politica de retencao",
    },
    {
        "entidade": "generations",
        "dados": ["cliente", "fatos", "pedidos", "fundamentos", "contexto usado", "texto gerado"],
        "base_operacional": "execucao do servico de geracao de minutas",
        "retencao": "quarentena apos exclusao e limpeza pela politica de retencao",
    },
    {
        "entidade": "writing_profiles",
        "dados": ["nome do advogado", "escritorio", "preferencias de escrita", "expressoes recorrentes"],
        "base_operacional": "personalizacao do servico",
        "retencao": "quarentena apos exclusao e limpeza pela politica de retencao",
    },
    {
        "entidade": "audit_logs",
        "dados": ["acao", "data", "usuario", "metadados tecnicos de seguranca"],
        "base_operacional": "seguranca, prevencao a abuso e rastreabilidade administrativa",
        "retencao": "limpeza pela politica de retencao de auditoria",
    },
]


@dataclass
class LGPDAnonymizationReport:
    user_id: int
    documents: int = 0
    generations: int = 0
    writing_profiles: int = 0
    audit_logs_scrubbed: int = 0
    files_deleted: int = 0
    files_missing: int = 0
    files_blocked: int = 0
    file_errors: list[str] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return self.documents + self.generations + self.writing_profiles + self.audit_logs_scrubbed

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "documents": self.documents,
            "generations": self.generations,
            "writing_profiles": self.writing_profiles,
            "audit_logs_scrubbed": self.audit_logs_scrubbed,
            "files_deleted": self.files_deleted,
            "files_missing": self.files_missing,
            "files_blocked": self.files_blocked,
            "file_errors": list(self.file_errors),
            "total_records": self.total_records,
        }


def obter_inventario_lgpd(db: Session) -> dict[str, Any]:
    return {
        "catalogo": CATALOGO_DADOS_LGPD,
        "totais": {
            "users": db.query(User).count(),
            "documents": db.query(Document).count(),
            "generations": db.query(Generation).count(),
            "writing_profiles": db.query(WritingProfile).count(),
            "audit_logs": db.query(AuditLog).count(),
        },
        "controles": [
            "controle de acesso por sessao",
            "soft delete para conteudos do usuario",
            "politica de retencao para exclusoes e auditoria",
            "auditoria de acoes sensiveis",
            "exportacao estruturada dos dados do titular",
            "anonimizacao administrativa do titular",
        ],
    }


def exportar_dados_titular_lgpd(db: Session, user_id: int) -> dict[str, Any] | None:
    usuario = db.query(User).filter(User.id == user_id).first()
    if not usuario:
        return None

    return {
        "exported_at": agora_brasil().isoformat(),
        "user": _serialize_user(usuario),
        "documents": [
            _serialize_document(documento)
            for documento in db.query(Document).filter(Document.user_id == user_id).order_by(Document.id.asc()).all()
        ],
        "generations": [
            _serialize_generation(geracao)
            for geracao in db.query(Generation).filter(Generation.user_id == user_id).order_by(Generation.id.asc()).all()
        ],
        "writing_profiles": [
            _serialize_writing_profile(perfil)
            for perfil in db.query(WritingProfile).filter(WritingProfile.user_id == user_id).order_by(WritingProfile.id.asc()).all()
        ],
        "audit_logs": [
            _serialize_audit_log(evento)
            for evento in db.query(AuditLog).filter(AuditLog.user_id == user_id).order_by(AuditLog.id.asc()).all()
        ],
    }


def anonimizar_titular_lgpd(
    db: Session,
    *,
    user_id: int,
    admin_atual: User,
    motivo: str = "solicitacao_lgpd",
) -> tuple[bool, str, LGPDAnonymizationReport | None]:
    usuario = db.query(User).filter(User.id == user_id).first()
    if not usuario:
        return False, "Usuario nao encontrado.", None
    if usuario.id == admin_atual.id:
        return False, "Voce nao pode anonimizar a propria conta administradora.", None

    agora = agora_brasil()
    report = LGPDAnonymizationReport(user_id=user_id)

    for documento in db.query(Document).filter(Document.user_id == user_id).all():
        _remover_arquivo_documento(documento, report)
        _anonimizar_documento(documento, agora)
        report.documents += 1
        db.add(documento)

    for geracao in db.query(Generation).filter(Generation.user_id == user_id).all():
        _anonimizar_geracao(geracao, agora)
        report.generations += 1
        db.add(geracao)

    for perfil in db.query(WritingProfile).filter(WritingProfile.user_id == user_id).all():
        _anonimizar_perfil(perfil, agora)
        report.writing_profiles += 1
        db.add(perfil)

    for evento in db.query(AuditLog).filter(AuditLog.user_id == user_id).all():
        _reduzir_payload_auditoria(evento)
        report.audit_logs_scrubbed += 1
        db.add(evento)

    usuario.full_name = f"Usuario anonimizado #{usuario.id}"
    usuario.email = f"anonimizado+{usuario.id}@juridico-ai.local"
    usuario.password_hash = "lgpd-anonymized"
    usuario.is_active = False
    usuario.is_admin = False
    usuario.plan_slug = "free"
    usuario.updated_at = agora
    db.add(usuario)

    registrar_acao_usuario(
        db,
        action="admin_lgpd_anonymize_user",
        usuario=admin_atual,
        metadata={"target_user_id": user_id, "motivo": motivo, "report": report.to_dict()},
        commit=False,
    )

    db.commit()
    return True, "Titular anonimizado e conteudos colocados em quarentena LGPD.", report


def _normalizar_data(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor else None


def _serialize_user(usuario: User) -> dict[str, Any]:
    return {
        "id": usuario.id,
        "full_name": usuario.full_name,
        "email": usuario.email,
        "is_active": bool(usuario.is_active),
        "is_admin": bool(usuario.is_admin),
        "plan_slug": usuario.plan_slug,
        "created_at": _normalizar_data(usuario.created_at),
        "updated_at": _normalizar_data(usuario.updated_at),
    }


def _serialize_document(documento: Document) -> dict[str, Any]:
    return {
        "id": documento.id,
        "original_filename": documento.original_filename,
        "file_type": documento.file_type,
        "extracted_text": documento.extracted_text,
        "tags": documento.tags,
        "status": documento.status,
        "is_favorite": bool(documento.is_favorite),
        "version": documento.version,
        "created_at": _normalizar_data(documento.created_at),
        "updated_at": _normalizar_data(documento.updated_at),
        "deleted_at": _normalizar_data(documento.deleted_at),
    }


def _serialize_generation(geracao: Generation) -> dict[str, Any]:
    return {
        "id": geracao.id,
        "client_name": geracao.client_name,
        "document_type": geracao.document_type,
        "case_subject": geracao.case_subject,
        "facts": geracao.facts,
        "requests": geracao.requests,
        "legal_basis": geracao.legal_basis,
        "context_used": geracao.context_used,
        "generated_text": geracao.generated_text,
        "document_ids": geracao.document_ids,
        "writing_profile_id": geracao.writing_profile_id,
        "tags": geracao.tags,
        "status": geracao.status,
        "version": geracao.version,
        "created_at": _normalizar_data(geracao.created_at),
        "updated_at": _normalizar_data(geracao.updated_at),
        "deleted_at": _normalizar_data(geracao.deleted_at),
    }


def _serialize_writing_profile(perfil: WritingProfile) -> dict[str, Any]:
    return {
        "id": perfil.id,
        "profile_name": perfil.profile_name,
        "lawyer_name": perfil.lawyer_name,
        "office_name": perfil.office_name,
        "tone": perfil.tone,
        "qualification_style": perfil.qualification_style,
        "opening_phrase": perfil.opening_phrase,
        "closing_phrase": perfil.closing_phrase,
        "request_intro": perfil.request_intro,
        "legal_style_notes": perfil.legal_style_notes,
        "recurring_expressions": perfil.recurring_expressions,
        "is_active": bool(perfil.is_active),
        "is_pinned": bool(perfil.is_pinned),
        "is_favorite": bool(perfil.is_favorite),
        "tags": perfil.tags,
        "status": perfil.status,
        "version": perfil.version,
        "created_at": _normalizar_data(perfil.created_at),
        "updated_at": _normalizar_data(perfil.updated_at),
        "deleted_at": _normalizar_data(perfil.deleted_at),
    }


def _serialize_audit_log(evento: AuditLog) -> dict[str, Any]:
    return {
        "id": evento.id,
        "entity_type": evento.entity_type,
        "entity_id": evento.entity_id,
        "action": evento.action,
        "entity_version": evento.entity_version,
        "payload": evento.payload,
        "created_at": _normalizar_data(evento.created_at),
    }


def _remover_arquivo_documento(documento: Document, report: LGPDAnonymizationReport) -> None:
    caminho_texto = (documento.file_path or "").strip()
    if not caminho_texto:
        report.files_missing += 1
        return

    try:
        caminho = proteger_path_documento(Path(caminho_texto))
    except ValueError:
        report.files_blocked += 1
        return

    if not caminho.is_file():
        report.files_missing += 1
        return

    try:
        caminho.unlink()
    except OSError as exc:
        report.file_errors.append(f"{documento.id}: {exc}")
        return

    report.files_deleted += 1


def _anonimizar_documento(documento: Document, agora: datetime) -> None:
    documento.original_filename = f"documento-lgpd-{documento.id}"
    documento.saved_filename = f"documento-lgpd-{documento.id}"
    documento.file_path = ""
    documento.file_type = "lgpd"
    documento.extracted_text = LGPD_PLACEHOLDER
    documento.tags = None
    documento.status = "anonimizado_lgpd"
    documento.is_favorite = False
    documento.deleted_at = documento.deleted_at or agora
    documento.updated_at = agora
    documento.version = int(getattr(documento, "version", 1) or 1) + 1


def _anonimizar_geracao(geracao: Generation, agora: datetime) -> None:
    geracao.client_name = LGPD_PLACEHOLDER
    geracao.case_subject = LGPD_PLACEHOLDER
    geracao.facts = LGPD_PLACEHOLDER
    geracao.requests = LGPD_PLACEHOLDER
    geracao.legal_basis = LGPD_PLACEHOLDER
    geracao.context_used = LGPD_PLACEHOLDER
    geracao.generated_text = LGPD_PLACEHOLDER
    geracao.llm_response_id = None
    geracao.llm_error = None
    geracao.source_document_ids = None
    geracao.documents = []
    geracao.writing_profile_id = None
    geracao.tags = None
    geracao.status = "anonimizado_lgpd"
    geracao.is_pinned = False
    geracao.is_favorite = False
    geracao.deleted_at = geracao.deleted_at or agora
    geracao.updated_at = agora
    geracao.version = int(getattr(geracao, "version", 1) or 1) + 1


def _anonimizar_perfil(perfil: WritingProfile, agora: datetime) -> None:
    perfil.profile_name = f"Perfil anonimizado #{perfil.id}"
    perfil.lawyer_name = None
    perfil.office_name = None
    perfil.tone = "Anonimizado"
    perfil.qualification_style = LGPD_PLACEHOLDER
    perfil.opening_phrase = LGPD_PLACEHOLDER
    perfil.closing_phrase = LGPD_PLACEHOLDER
    perfil.request_intro = LGPD_PLACEHOLDER
    perfil.legal_style_notes = LGPD_PLACEHOLDER
    perfil.recurring_expressions = LGPD_PLACEHOLDER
    perfil.is_active = False
    perfil.is_pinned = False
    perfil.is_favorite = False
    perfil.tags = None
    perfil.status = "anonimizado_lgpd"
    perfil.deleted_at = perfil.deleted_at or agora
    perfil.updated_at = agora
    perfil.version = int(getattr(perfil, "version", 1) or 1) + 1


def _reduzir_payload_auditoria(evento: AuditLog) -> None:
    evento.payload = json.dumps(
        {
            "lgpd_scrubbed": True,
            "user_id": evento.user_id,
            "original_action": evento.action,
        },
        ensure_ascii=True,
        sort_keys=True,
    )
