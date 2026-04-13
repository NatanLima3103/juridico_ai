import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import Base, get_db
from app.models.document import Document
from app.routers import auth, documents
from app.schemas.user import UserCreate
from app.services.user_service import criar_usuario


def create_documents_test_client() -> tuple[TestClient, sessionmaker]:
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
    app.include_router(documents.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


def criar_usuario_teste(testing_session_local, *, nome: str, email: str):
    db = testing_session_local()
    try:
        return criar_usuario(
            db,
            UserCreate(
                full_name=nome,
                email=email,
                password="senha1234",
            ),
        )
    finally:
        db.close()


def criar_documento_teste(testing_session_local, *, user_id: int, nome_arquivo: str) -> Document:
    db = testing_session_local()
    try:
        documento = Document(
            original_filename=nome_arquivo,
            saved_filename=nome_arquivo,
            file_path=f"C:/tmp/{nome_arquivo}",
            file_type=Path(nome_arquivo).suffix.lower() or ".txt",
            extracted_text=f"Conteudo de {nome_arquivo}",
            user_id=user_id,
        )
        db.add(documento)
        db.commit()
        db.refresh(documento)
        return documento
    finally:
        db.close()


def fazer_login(client: TestClient, *, email: str):
    resposta = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "senha1234",
        },
        follow_redirects=False,
    )
    assert resposta.status_code == 303


class DocumentsOwnershipTests(unittest.TestCase):
    def test_documents_list_shows_only_authenticated_user_documents(self):
        client, testing_session_local = create_documents_test_client()
        usuario_1 = criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        usuario_2 = criar_usuario_teste(testing_session_local, nome="Bruno Lima", email="bruno@example.com")

        criar_documento_teste(testing_session_local, user_id=usuario_1.id, nome_arquivo="contrato-ana.pdf")
        criar_documento_teste(testing_session_local, user_id=usuario_2.id, nome_arquivo="contrato-bruno.pdf")

        fazer_login(client, email="ana@example.com")

        response = client.get("/documents")

        self.assertEqual(response.status_code, 200)
        self.assertIn("contrato-ana.pdf", response.text)
        self.assertNotIn("contrato-bruno.pdf", response.text)

    def test_document_detail_returns_404_for_document_from_another_user(self):
        client, testing_session_local = create_documents_test_client()
        usuario_1 = criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        usuario_2 = criar_usuario_teste(testing_session_local, nome="Bruno Lima", email="bruno@example.com")

        documento_bruno = criar_documento_teste(
            testing_session_local,
            user_id=usuario_2.id,
            nome_arquivo="peticao-bruno.pdf",
        )

        fazer_login(client, email="ana@example.com")

        response = client.get(f"/documents/{documento_bruno.id}")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Documento n", response.text)

    def test_upload_links_document_to_authenticated_user(self):
        client, testing_session_local = create_documents_test_client()
        usuario = criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        fazer_login(client, email="ana@example.com")

        arquivo_salvo = Path(".tmp_pytest") / "upload-ana.pdf"
        arquivo_salvo.write_text("arquivo de teste", encoding="utf-8")

        async def fake_salvar_arquivo_upload(_file):
            return arquivo_salvo

        with patch("app.routers.documents.salvar_arquivo_upload", fake_salvar_arquivo_upload), patch(
            "app.routers.documents.extrair_texto_arquivo",
            return_value="texto extraido",
        ):
            response = client.post(
                "/documents/upload",
                files={"file": ("upload-ana.pdf", b"conteudo fake", "application/pdf")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Documento enviado e salvo com sucesso.", response.text)

        db = testing_session_local()
        try:
            documentos_usuario = db.query(Document).filter(Document.user_id == usuario.id).all()
            self.assertEqual(len(documentos_usuario), 1)
            self.assertEqual(documentos_usuario[0].original_filename, "upload-ana.pdf")
            self.assertEqual(documentos_usuario[0].user_id, usuario.id)
        finally:
            db.close()


    def test_delete_document_soft_deletes_record(self):
        client, testing_session_local = create_documents_test_client()
        usuario = criar_usuario_teste(testing_session_local, nome="Ana Souza", email="ana@example.com")
        documento = criar_documento_teste(
            testing_session_local,
            user_id=usuario.id,
            nome_arquivo="contrato-soft-delete.pdf",
        )

        fazer_login(client, email="ana@example.com")

        response = client.post(f"/documents/{documento.id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 303)

        db = testing_session_local()
        try:
            documento_db = db.query(Document).filter(Document.id == documento.id).first()
            self.assertIsNotNone(documento_db)
            self.assertIsNotNone(documento_db.deleted_at)
        finally:
            db.close()

        list_response = client.get("/documents")

        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn("contrato-soft-delete.pdf", list_response.text)


if __name__ == "__main__":
    unittest.main()
