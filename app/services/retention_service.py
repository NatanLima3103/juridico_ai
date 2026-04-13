from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import AUDIT_LOG_RETENTION_DAYS, SOFT_DELETED_RETENTION_DAYS
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.generation import Generation
from app.models.user import User
from app.models.writing_profile import WritingProfile
from app.services.audit_service import registrar_acao_usuario
from app.services.document_service import proteger_path_documento


@dataclass
class RetentionPolicy:
    soft_deleted_days: int = SOFT_DELETED_RETENTION_DAYS
    audit_log_days: int = AUDIT_LOG_RETENTION_DAYS


@dataclass
class RetentionReport:
    cutoff_soft_deleted: datetime
    cutoff_audit_logs: datetime
    documents: int = 0
    generations: int = 0
    writing_profiles: int = 0
    audit_logs: int = 0
    files_deleted: int = 0
    files_missing: int = 0
    files_blocked: int = 0
    file_errors: list[str] = field(default_factory=list)
    dry_run: bool = True

    @property
    def total_records(self) -> int:
        return self.documents + self.generations + self.writing_profiles + self.audit_logs

    def to_dict(self) -> dict[str, Any]:
        return {
            "cutoff_soft_deleted": self.cutoff_soft_deleted,
            "cutoff_audit_logs": self.cutoff_audit_logs,
            "documents": self.documents,
            "generations": self.generations,
            "writing_profiles": self.writing_profiles,
            "audit_logs": self.audit_logs,
            "files_deleted": self.files_deleted,
            "files_missing": self.files_missing,
            "files_blocked": self.files_blocked,
            "file_errors": list(self.file_errors),
            "dry_run": self.dry_run,
            "total_records": self.total_records,
        }


def obter_politica_retencao() -> RetentionPolicy:
    return RetentionPolicy(
        soft_deleted_days=max(1, int(SOFT_DELETED_RETENTION_DAYS)),
        audit_log_days=max(1, int(AUDIT_LOG_RETENTION_DAYS)),
    )


def _calcular_cortes(policy: RetentionPolicy, agora: datetime | None = None) -> tuple[datetime, datetime]:
    referencia = agora or datetime.now()
    return (
        referencia - timedelta(days=max(1, int(policy.soft_deleted_days))),
        referencia - timedelta(days=max(1, int(policy.audit_log_days))),
    )


def resumir_retencao(
    db: Session,
    *,
    policy: RetentionPolicy | None = None,
    agora: datetime | None = None,
) -> RetentionReport:
    policy = policy or obter_politica_retencao()
    cutoff_soft_deleted, cutoff_audit_logs = _calcular_cortes(policy, agora)

    return RetentionReport(
        cutoff_soft_deleted=cutoff_soft_deleted,
        cutoff_audit_logs=cutoff_audit_logs,
        documents=(
            db.query(Document)
            .filter(Document.deleted_at.is_not(None), Document.deleted_at < cutoff_soft_deleted)
            .count()
        ),
        generations=(
            db.query(Generation)
            .filter(Generation.deleted_at.is_not(None), Generation.deleted_at < cutoff_soft_deleted)
            .count()
        ),
        writing_profiles=(
            db.query(WritingProfile)
            .filter(WritingProfile.deleted_at.is_not(None), WritingProfile.deleted_at < cutoff_soft_deleted)
            .count()
        ),
        audit_logs=db.query(AuditLog).filter(AuditLog.created_at < cutoff_audit_logs).count(),
        dry_run=True,
    )


def aplicar_politica_retencao(
    db: Session,
    *,
    policy: RetentionPolicy | None = None,
    admin_atual: User | None = None,
    agora: datetime | None = None,
) -> RetentionReport:
    policy = policy or obter_politica_retencao()
    cutoff_soft_deleted, cutoff_audit_logs = _calcular_cortes(policy, agora)
    report = RetentionReport(
        cutoff_soft_deleted=cutoff_soft_deleted,
        cutoff_audit_logs=cutoff_audit_logs,
        dry_run=False,
    )

    documentos = (
        db.query(Document)
        .filter(Document.deleted_at.is_not(None), Document.deleted_at < cutoff_soft_deleted)
        .all()
    )
    report.documents = len(documentos)
    for documento in documentos:
        _remover_arquivo_documento(documento, report)
        db.delete(documento)

    geracoes = (
        db.query(Generation)
        .filter(Generation.deleted_at.is_not(None), Generation.deleted_at < cutoff_soft_deleted)
        .all()
    )
    report.generations = len(geracoes)
    for geracao in geracoes:
        db.delete(geracao)

    perfis = (
        db.query(WritingProfile)
        .filter(WritingProfile.deleted_at.is_not(None), WritingProfile.deleted_at < cutoff_soft_deleted)
        .all()
    )
    report.writing_profiles = len(perfis)
    for perfil in perfis:
        db.delete(perfil)

    auditorias = db.query(AuditLog).filter(AuditLog.created_at < cutoff_audit_logs).all()
    report.audit_logs = len(auditorias)
    for evento in auditorias:
        db.delete(evento)

    if admin_atual is not None:
        registrar_acao_usuario(
            db,
            action="admin_apply_retention_policy",
            usuario=admin_atual,
            metadata=report.to_dict(),
            commit=False,
        )

    db.commit()
    return report


def _remover_arquivo_documento(documento: Document, report: RetentionReport) -> None:
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
