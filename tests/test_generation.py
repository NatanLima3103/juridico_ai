import unittest

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import Base, get_db
from app.models.audit_log import AuditLog
from app.models.generation import Generation
from app.routers import auth, generations
from app.schemas.user import UserCreate
from app.services.user_service import criar_usuario


def create_generation_test_client() -> tuple[TestClient, sessionmaker]:
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
    app.include_router(generations.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


def create_user_for_test(testing_session_local: sessionmaker, *, full_name: str, email: str):
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


def authenticate_test_client(client: TestClient, *, email: str) -> None:
    response = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "senha1234",
            "next": "/generations",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


class GenerationsOwnershipTests(unittest.TestCase):
    def test_create_generation_links_record_to_authenticated_user(self):
        client, testing_session_local = create_generation_test_client()
        usuario = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        authenticate_test_client(client, email="maria@example.com")

        response = client.post(
            "/generations/create",
            data={
                "client_name": "Cliente Teste",
                "document_type": "Petição inicial",
                "case_subject": "Cobrança indevida em contrato",
                "facts": "O cliente relata cobrança indevida reiterada e apresentou documentos que demonstram a falha contratual.",
                "requests": "Cancelamento da cobrança e indenização pelos danos causados.",
                "legal_basis": "Código Civil e Código de Defesa do Consumidor.",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn("/generations/1?sucesso=", response.headers["location"])

        db = testing_session_local()
        try:
            geracao = db.query(Generation).filter(Generation.id == 1).first()
            self.assertIsNotNone(geracao)
            self.assertEqual(geracao.user_id, usuario.id)
            self.assertEqual(geracao.client_name, "Cliente Teste")
            self.assertEqual(geracao.generation_strategy, "rule_based")
            self.assertIsNone(geracao.llm_provider)

            auditoria = db.query(AuditLog).filter(AuditLog.entity_type == "generation", AuditLog.entity_id == geracao.id).first()
            self.assertIsNotNone(auditoria)
            self.assertEqual(auditoria.user_id, usuario.id)
        finally:
            db.close()

    def test_list_generations_shows_only_authenticated_user_records(self):
        client, testing_session_local = create_generation_test_client()
        usuario_1 = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        usuario_2 = create_user_for_test(testing_session_local, full_name="Ana Souza", email="ana@example.com")

        db = testing_session_local()
        try:
            db.add(
                Generation(
                    user_id=usuario_1.id,
                    client_name="Cliente Maria",
                    document_type="Petição inicial",
                    case_subject="Assunto Maria",
                    facts="Fatos suficientemente detalhados para a geração da peça da Maria.",
                    requests="Pedidos da Maria devidamente descritos.",
                    legal_basis="Base legal Maria.",
                    context_used="Contexto Maria.",
                    generated_text="Texto gerado Maria.",
                )
            )
            db.add(
                Generation(
                    user_id=usuario_2.id,
                    client_name="Cliente Ana",
                    document_type="Petição inicial",
                    case_subject="Assunto Ana",
                    facts="Fatos suficientemente detalhados para a geração da peça da Ana.",
                    requests="Pedidos da Ana devidamente descritos.",
                    legal_basis="Base legal Ana.",
                    context_used="Contexto Ana.",
                    generated_text="Texto gerado Ana.",
                )
            )
            db.commit()
        finally:
            db.close()

        authenticate_test_client(client, email="maria@example.com")

        response = client.get("/generations")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Cliente Maria", response.text)
        self.assertNotIn("Cliente Ana", response.text)

    def test_generation_detail_returns_404_for_generation_from_other_user(self):
        client, testing_session_local = create_generation_test_client()
        create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        usuario_2 = create_user_for_test(testing_session_local, full_name="Ana Souza", email="ana@example.com")

        db = testing_session_local()
        try:
            geracao = Generation(
                user_id=usuario_2.id,
                client_name="Cliente Ana",
                document_type="Petição inicial",
                case_subject="Assunto Ana",
                facts="Fatos suficientemente detalhados para a geração da peça da Ana.",
                requests="Pedidos da Ana devidamente descritos.",
                legal_basis="Base legal Ana.",
                context_used="Contexto Ana.",
                generated_text="Texto gerado Ana.",
            )
            db.add(geracao)
            db.commit()
            db.refresh(geracao)
            geracao_id = geracao.id
        finally:
            db.close()

        authenticate_test_client(client, email="maria@example.com")

        response = client.get(f"/generations/{geracao_id}")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Gera", response.text)


if __name__ == "__main__":
    unittest.main()
