import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.generation import Generation
from app.models.writing_profile import WritingProfile
from app.services.retention_service import RetentionPolicy, aplicar_politica_retencao, resumir_retencao


def create_retention_session() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


class RetentionPolicyTests(unittest.TestCase):
    def test_retention_summary_counts_only_records_outside_policy(self):
        testing_session_local = create_retention_session()
        agora = datetime(2026, 4, 13, 12, 0, 0)

        db = testing_session_local()
        try:
            db.add(
                Document(
                    original_filename="antigo.pdf",
                    saved_filename="antigo.pdf",
                    file_path="storage/uploads/antigo.pdf",
                    file_type=".pdf",
                    extracted_text="Documento antigo.",
                    user_id=None,
                    deleted_at=agora - timedelta(days=31),
                )
            )
            db.add(
                Document(
                    original_filename="recente.pdf",
                    saved_filename="recente.pdf",
                    file_path="storage/uploads/recente.pdf",
                    file_type=".pdf",
                    extracted_text="Documento recente.",
                    user_id=None,
                    deleted_at=agora - timedelta(days=5),
                )
            )
            db.add(
                AuditLog(
                    user_id=None,
                    entity_type="document",
                    entity_id=1,
                    action="create",
                    entity_version=1,
                    payload="{}",
                    created_at=agora - timedelta(days=181),
                )
            )
            db.add(
                AuditLog(
                    user_id=None,
                    entity_type="document",
                    entity_id=2,
                    action="create",
                    entity_version=1,
                    payload="{}",
                    created_at=agora - timedelta(days=30),
                )
            )
            db.commit()

            report = resumir_retencao(
                db,
                policy=RetentionPolicy(soft_deleted_days=30, audit_log_days=180),
                agora=agora,
            )

            self.assertEqual(report.documents, 1)
            self.assertEqual(report.audit_logs, 1)
            self.assertEqual(report.total_records, 2)
        finally:
            db.close()

    def test_apply_retention_purges_old_soft_deleted_records_and_files(self):
        testing_session_local = create_retention_session()
        agora = datetime(2026, 4, 13, 12, 0, 0)
        upload_path_teste = Path(".tmp_pytest") / "retention-uploads"
        upload_path_teste.mkdir(parents=True, exist_ok=True)
        arquivo_antigo = upload_path_teste / "antigo.pdf"
        arquivo_antigo.write_text("conteudo antigo", encoding="utf-8")

        db = testing_session_local()
        try:
            documento = Document(
                original_filename="antigo.pdf",
                saved_filename="antigo.pdf",
                file_path=str(arquivo_antigo),
                file_type=".pdf",
                extracted_text="Documento antigo.",
                user_id=None,
                deleted_at=agora - timedelta(days=45),
            )
            geracao = Generation(
                user_id=None,
                client_name="Cliente Antigo",
                document_type="Peticao inicial",
                case_subject="Assunto antigo",
                facts="Fatos antigos suficientes.",
                requests="Pedidos antigos.",
                legal_basis="Base antiga.",
                context_used="Contexto antigo.",
                generated_text="Texto antigo.",
                deleted_at=agora - timedelta(days=45),
            )
            perfil = WritingProfile(
                user_id=None,
                profile_name="Perfil Antigo",
                deleted_at=agora - timedelta(days=45),
            )
            auditoria_antiga = AuditLog(
                user_id=None,
                entity_type="generation",
                entity_id=1,
                action="create",
                entity_version=1,
                payload="{}",
                created_at=agora - timedelta(days=200),
            )
            auditoria_recente = AuditLog(
                user_id=None,
                entity_type="generation",
                entity_id=2,
                action="create",
                entity_version=1,
                payload="{}",
                created_at=agora - timedelta(days=2),
            )
            db.add_all([documento, geracao, perfil, auditoria_antiga, auditoria_recente])
            db.commit()
            auditoria_recente_id = auditoria_recente.id

            from app.services import document_service

            original_upload_path = document_service.UPLOAD_PATH
            try:
                document_service.UPLOAD_PATH = upload_path_teste
                with patch.object(Path, "unlink", return_value=None) as unlink_mock:
                    report = aplicar_politica_retencao(
                        db,
                        policy=RetentionPolicy(soft_deleted_days=30, audit_log_days=180),
                        agora=agora,
                    )
            finally:
                document_service.UPLOAD_PATH = original_upload_path

            self.assertEqual(report.documents, 1)
            self.assertEqual(report.generations, 1)
            self.assertEqual(report.writing_profiles, 1)
            self.assertEqual(report.audit_logs, 1)
            self.assertEqual(report.files_deleted, 1)
            unlink_mock.assert_called_once()
            self.assertEqual(db.query(Document).count(), 0)
            self.assertEqual(db.query(Generation).count(), 0)
            self.assertEqual(db.query(WritingProfile).count(), 0)
            self.assertEqual(db.query(AuditLog).count(), 1)
            self.assertEqual(db.query(AuditLog).first().id, auditoria_recente_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
