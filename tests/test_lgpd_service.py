import unittest
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
from app.schemas.user import UserCreate
from app.services.lgpd_service import (
    LGPD_PLACEHOLDER,
    anonimizar_titular_lgpd,
    exportar_dados_titular_lgpd,
    obter_inventario_lgpd,
)
from app.services.user_service import criar_usuario


def create_lgpd_session() -> sessionmaker:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return testing_session_local


class LGPDServiceTests(unittest.TestCase):
    def test_inventory_and_export_include_user_owned_data(self):
        testing_session_local = create_lgpd_session()
        db = testing_session_local()
        try:
            usuario = criar_usuario(
                db,
                UserCreate(full_name="Titular Dados", email="titular@example.com", password="senha1234"),
            )
            db.add(
                Document(
                    original_filename="contrato.pdf",
                    saved_filename="contrato.pdf",
                    file_path="storage/uploads/contrato.pdf",
                    file_type=".pdf",
                    extracted_text="Texto com dados pessoais.",
                    user_id=usuario.id,
                )
            )
            db.add(
                Generation(
                    user_id=usuario.id,
                    client_name="Cliente Exportado",
                    document_type="Peticao inicial",
                    case_subject="Assunto sensivel",
                    facts="Fatos sensiveis",
                    requests="Pedidos",
                    legal_basis="Base",
                    context_used="Contexto",
                    generated_text="Texto gerado",
                )
            )
            db.commit()

            inventario = obter_inventario_lgpd(db)
            exportacao = exportar_dados_titular_lgpd(db, usuario.id)

            self.assertEqual(inventario["totais"]["users"], 1)
            self.assertEqual(exportacao["user"]["email"], "titular@example.com")
            self.assertEqual(exportacao["documents"][0]["extracted_text"], "Texto com dados pessoais.")
            self.assertEqual(exportacao["generations"][0]["client_name"], "Cliente Exportado")
        finally:
            db.close()

    def test_anonymization_scrubs_content_deactivates_user_and_removes_allowed_file(self):
        testing_session_local = create_lgpd_session()
        upload_path_teste = Path(".tmp_pytest") / "lgpd-uploads"
        upload_path_teste.mkdir(parents=True, exist_ok=True)
        arquivo = upload_path_teste / "dados.pdf"
        arquivo.write_text("conteudo sensivel", encoding="utf-8")

        db = testing_session_local()
        try:
            admin = criar_usuario(
                db,
                UserCreate(full_name="Admin LGPD", email="admin-lgpd@example.com", password="senha1234"),
            )
            titular = criar_usuario(
                db,
                UserCreate(full_name="Titular LGPD", email="titular-lgpd@example.com", password="senha1234"),
            )
            db.add_all(
                [
                    Document(
                        original_filename="dados.pdf",
                        saved_filename="dados.pdf",
                        file_path=str(arquivo),
                        file_type=".pdf",
                        extracted_text="Nome e CPF do cliente.",
                        user_id=titular.id,
                    ),
                    Generation(
                        user_id=titular.id,
                        client_name="Cliente Sensivel",
                        document_type="Peticao inicial",
                        case_subject="Assunto sensivel",
                        facts="Fatos sensiveis",
                        requests="Pedidos sensiveis",
                        legal_basis="Base sensivel",
                        context_used="Contexto sensivel",
                        generated_text="Texto sensivel",
                    ),
                    WritingProfile(
                        user_id=titular.id,
                        profile_name="Perfil Sensivel",
                        lawyer_name="Advogada Titular",
                        office_name="Escritorio Titular",
                    ),
                    AuditLog(
                        user_id=titular.id,
                        entity_type="generation",
                        entity_id=1,
                        action="create",
                        entity_version=1,
                        payload='{"client_name": "Cliente Sensivel"}',
                    ),
                ]
            )
            db.commit()

            with patch("app.services.document_service.UPLOAD_PATH", upload_path_teste):
                with patch.object(Path, "unlink", return_value=None) as unlink_mock:
                    sucesso, mensagem, relatorio = anonimizar_titular_lgpd(
                        db,
                        user_id=titular.id,
                        admin_atual=admin,
                    )

            self.assertTrue(sucesso)
            self.assertIn("Titular anonimizado", mensagem)
            self.assertEqual(relatorio.files_deleted, 1)
            unlink_mock.assert_called_once()

            db.refresh(titular)
            documento = db.query(Document).filter(Document.user_id == titular.id).first()
            geracao = db.query(Generation).filter(Generation.user_id == titular.id).first()
            perfil = db.query(WritingProfile).filter(WritingProfile.user_id == titular.id).first()
            auditoria = db.query(AuditLog).filter(AuditLog.user_id == titular.id).first()

            self.assertFalse(titular.is_active)
            self.assertEqual(titular.email, f"anonimizado+{titular.id}@juridico-ai.local")
            self.assertEqual(documento.extracted_text, LGPD_PLACEHOLDER)
            self.assertIsNotNone(documento.deleted_at)
            self.assertEqual(geracao.client_name, LGPD_PLACEHOLDER)
            self.assertIsNotNone(geracao.deleted_at)
            self.assertEqual(perfil.lawyer_name, None)
            self.assertIsNotNone(perfil.deleted_at)
            self.assertIn("lgpd_scrubbed", auditoria.payload)
        finally:
            db.close()

    def test_admin_cannot_anonymize_own_account(self):
        testing_session_local = create_lgpd_session()
        db = testing_session_local()
        try:
            admin = criar_usuario(
                db,
                UserCreate(full_name="Admin LGPD", email="admin-self@example.com", password="senha1234"),
            )

            sucesso, mensagem, relatorio = anonimizar_titular_lgpd(
                db,
                user_id=admin.id,
                admin_atual=admin,
            )

            self.assertFalse(sucesso)
            self.assertIsNone(relatorio)
            self.assertIn("propria conta", mensagem)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
