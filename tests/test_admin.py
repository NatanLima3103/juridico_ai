import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware
from unittest.mock import patch

from app.core.config import SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import Base, get_db
from app.models.document import Document
from app.models.generation import Generation
from app.models.user import User
from app.routers import admin, auth
from app.schemas.user import UserCreate
from app.services.user_service import criar_usuario


def create_admin_test_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key=SECRET_KEY,
        session_cookie=SESSION_COOKIE_NAME,
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    app.include_router(auth.router)
    app.include_router(admin.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


def create_user(testing_session_local: sessionmaker, *, full_name: str, email: str):
    db = testing_session_local()
    try:
        return criar_usuario(
            db,
            UserCreate(
                full_name=full_name,
                email=email,
                password="senha1234",
            ),
        )
    finally:
        db.close()


def login(client: TestClient, *, email: str, next_url: str = "/admin") -> None:
    response = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "senha1234",
            "next": next_url,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


class AdminAreaTests(unittest.TestCase):
    def test_first_user_can_access_admin_dashboard(self):
        client, testing_session_local = create_admin_test_client()
        create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")

        login(client, email="admin@example.com")

        response = client.get("/admin")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Administração do sistema", response.text)

    def test_non_admin_user_is_redirected_from_admin_dashboard(self):
        client, testing_session_local = create_admin_test_client()
        create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")
        create_user(testing_session_local, full_name="Usuário Comum", email="user@example.com")

        login(client, email="user@example.com")

        response = client.get("/admin", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("/?erro=", response.headers["location"])

    def test_admin_cannot_delete_healthy_record_through_problem_records_route(self):
        client, testing_session_local = create_admin_test_client()
        admin_user = create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")

        db = testing_session_local()
        try:
            upload_path_teste = Path(".tmp_pytest") / "uploads-admin"
            upload_path_teste.mkdir(parents=True, exist_ok=True)
            arquivo_salvo = upload_path_teste / "documento-saudavel-admin.pdf"
            arquivo_salvo.write_text("documento saudavel", encoding="utf-8")
            documento = Document(
                original_filename="documento-saudavel.pdf",
                saved_filename="documento-saudavel.pdf",
                file_path=str(arquivo_salvo),
                file_type=".pdf",
                extracted_text="Documento saudavel.",
                user_id=admin_user.id,
            )
            db.add(documento)
            db.commit()
            db.refresh(documento)
            document_id = documento.id
        finally:
            db.close()

        login(client, email="admin@example.com")

        with patch("app.services.document_service.UPLOAD_PATH", upload_path_teste):
            response = client.post(f"/admin/problem-records/document/{document_id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("erro=", response.headers["location"])

        db = testing_session_local()
        try:
            documento_db = db.query(Document).filter(Document.id == document_id).first()
            self.assertIsNotNone(documento_db)
        finally:
            db.close()

    def test_admin_can_delete_problematic_record_through_problem_records_route(self):
        client, testing_session_local = create_admin_test_client()
        create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")

        db = testing_session_local()
        try:
            documento = Document(
                original_filename="documento-problematico.pdf",
                saved_filename="documento-problematico.pdf",
                file_path="storage/arquivo-inexistente-13-5.pdf",
                file_type=".pdf",
                extracted_text="Documento problematico.",
                user_id=None,
            )
            db.add(documento)
            db.commit()
            db.refresh(documento)
            document_id = documento.id
        finally:
            db.close()

        login(client, email="admin@example.com")

        response = client.post(f"/admin/problem-records/document/{document_id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("sucesso=", response.headers["location"])

        db = testing_session_local()
        try:
            documento_db = db.query(Document).filter(Document.id == document_id).first()
            self.assertIsNone(documento_db)
        finally:
            db.close()

    def test_admin_can_delete_document_record_outside_upload_storage(self):
        client, testing_session_local = create_admin_test_client()
        admin_user = create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")

        db = testing_session_local()
        try:
            documento = Document(
                original_filename="documento-fora-storage.pdf",
                saved_filename="documento-fora-storage.pdf",
                file_path="app/core/config.py",
                file_type=".pdf",
                extracted_text="Documento fora do armazenamento.",
                user_id=admin_user.id,
            )
            db.add(documento)
            db.commit()
            db.refresh(documento)
            document_id = documento.id
        finally:
            db.close()

        login(client, email="admin@example.com")

        response = client.post(f"/admin/problem-records/document/{document_id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("sucesso=", response.headers["location"])

        db = testing_session_local()
        try:
            documento_db = db.query(Document).filter(Document.id == document_id).first()
            self.assertIsNone(documento_db)
        finally:
            db.close()

    def test_admin_can_export_user_lgpd_data(self):
        client, testing_session_local = create_admin_test_client()
        create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")
        titular = create_user(testing_session_local, full_name="Titular Export", email="titular-export@example.com")

        db = testing_session_local()
        try:
            db.add(
                Generation(
                    user_id=titular.id,
                    client_name="Cliente Export LGPD",
                    document_type="Peticao inicial",
                    case_subject="Assunto",
                    facts="Fatos",
                    requests="Pedidos",
                    legal_basis="Base",
                    context_used="Contexto",
                    generated_text="Texto",
                )
            )
            db.commit()
        finally:
            db.close()

        login(client, email="admin@example.com")

        response = client.get(f"/admin/users/{titular.id}/lgpd-export")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["user"]["email"], "titular-export@example.com")
        self.assertEqual(payload["generations"][0]["client_name"], "Cliente Export LGPD")

    def test_admin_can_anonymize_user_lgpd_data(self):
        client, testing_session_local = create_admin_test_client()
        create_user(testing_session_local, full_name="Admin Inicial", email="admin@example.com")
        titular = create_user(testing_session_local, full_name="Titular Remove", email="titular-remove@example.com")

        db = testing_session_local()
        try:
            db.add(
                Generation(
                    user_id=titular.id,
                    client_name="Cliente Remove LGPD",
                    document_type="Peticao inicial",
                    case_subject="Assunto",
                    facts="Fatos",
                    requests="Pedidos",
                    legal_basis="Base",
                    context_used="Contexto",
                    generated_text="Texto",
                )
            )
            db.commit()
            titular_id = titular.id
        finally:
            db.close()

        login(client, email="admin@example.com")

        response = client.post(f"/admin/users/{titular_id}/lgpd-anonymize", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("sucesso=", response.headers["location"])

        db = testing_session_local()
        try:
            usuario_db = db.query(User).filter(User.id == titular_id).first()
            geracao_db = db.query(Generation).filter(Generation.user_id == titular_id).first()

            self.assertFalse(usuario_db.is_active)
            self.assertEqual(usuario_db.email, f"anonimizado+{titular_id}@juridico-ai.local")
            self.assertEqual(geracao_db.client_name, "[removido por solicitacao LGPD]")
            self.assertIsNotNone(geracao_db.deleted_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
