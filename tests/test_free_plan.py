from datetime import datetime
import unittest
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
from app.models.generation import Generation
from app.routers import auth, generations
from app.schemas.user import UserCreate
from app.services.plan_service import FREE_PLAN, PRO_PLAN, listar_planos_disponiveis, obter_uso_plano_usuario
from app.services.user_service import criar_usuario


def create_free_plan_test_client() -> tuple[TestClient, sessionmaker]:
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


def criar_usuario_teste(testing_session_local: sessionmaker, *, email: str = "free@example.com"):
    db = testing_session_local()
    try:
        return criar_usuario(
            db,
            UserCreate(
                full_name="Usuario Plano Free",
                email=email,
                password="senha1234",
            ),
        )
    finally:
        db.close()


def autenticar(client: TestClient, *, email: str = "free@example.com") -> None:
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


def criar_geracao_teste(db, *, user_id: int, created_at: datetime) -> None:
    db.add(
        Generation(
            user_id=user_id,
            client_name="Cliente Teste",
            document_type="Contrato",
            case_subject="Prestacao de servicos",
            facts="Fatos suficientemente detalhados para compor a minuta juridica.",
            requests="Pedidos suficientes para a geracao.",
            legal_basis="Codigo Civil.",
            context_used="Contexto",
            generated_text="Texto gerado",
            created_at=created_at,
            updated_at=created_at,
        )
    )


class FreePlanTests(unittest.TestCase):
    def test_new_user_starts_on_free_plan(self):
        _, testing_session_local = create_free_plan_test_client()
        usuario = criar_usuario_teste(testing_session_local)

        self.assertEqual(usuario.plan_slug, "free")

    def test_free_plan_usage_counts_only_current_month(self):
        _, testing_session_local = create_free_plan_test_client()
        usuario = criar_usuario_teste(testing_session_local)
        referencia = datetime(2026, 4, 10, 12, 0, 0)

        db = testing_session_local()
        try:
            criar_geracao_teste(db, user_id=usuario.id, created_at=datetime(2026, 4, 1, 8, 0, 0))
            criar_geracao_teste(db, user_id=usuario.id, created_at=datetime(2026, 3, 31, 23, 59, 0))
            db.commit()

            usage = obter_uso_plano_usuario(db, usuario, referencia=referencia)
        finally:
            db.close()

        self.assertEqual(usage.plan.slug, "free")
        self.assertEqual(usage.used_generations, 1)
        self.assertEqual(usage.remaining_generations, FREE_PLAN.monthly_generation_limit - 1)
        self.assertTrue(usage.can_create_generation)

    def test_free_plan_blocks_generation_when_monthly_limit_is_reached(self):
        client, testing_session_local = create_free_plan_test_client()
        usuario = criar_usuario_teste(testing_session_local)
        autenticar(client)

        db = testing_session_local()
        try:
            now = datetime.now()
            for _ in range(FREE_PLAN.monthly_generation_limit):
                criar_geracao_teste(db, user_id=usuario.id, created_at=now)
            db.commit()
        finally:
            db.close()

        with patch("app.routers.generations.gerar_rascunho_juridico_com_metadata") as gerar_mock:
            response = client.post(
                "/generations/create",
                data={
                    "client_name": "Cliente Teste",
                    "document_type": "Contrato",
                    "case_subject": "Prestacao de servicos",
                    "facts": "As partes pretendem formalizar uma prestacao de servicos continuada.",
                    "requests": "Definir objeto, prazo, pagamento e rescisao.",
                    "legal_basis": "Codigo Civil.",
                },
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Plano gratuito", response.text)
        self.assertIn("limite", response.text.lower())
        gerar_mock.assert_not_called()

    def test_paid_plan_is_defined_with_expanded_generation_limit(self):
        planos = listar_planos_disponiveis()

        self.assertIn(FREE_PLAN, planos)
        self.assertIn(PRO_PLAN, planos)
        self.assertEqual(PRO_PLAN.slug, "pro")
        self.assertGreater(PRO_PLAN.monthly_generation_limit, FREE_PLAN.monthly_generation_limit)

    def test_paid_plan_uses_its_own_monthly_limit(self):
        _, testing_session_local = create_free_plan_test_client()
        usuario = criar_usuario_teste(testing_session_local, email="pro@example.com")
        referencia = datetime(2026, 4, 10, 12, 0, 0)

        db = testing_session_local()
        try:
            usuario_db = db.merge(usuario)
            usuario_db.plan_slug = "pro"
            for _ in range(FREE_PLAN.monthly_generation_limit):
                criar_geracao_teste(db, user_id=usuario_db.id, created_at=referencia)
            db.commit()

            usage = obter_uso_plano_usuario(db, usuario_db, referencia=referencia)
        finally:
            db.close()

        self.assertEqual(usage.plan.slug, "pro")
        self.assertEqual(usage.used_generations, FREE_PLAN.monthly_generation_limit)
        self.assertEqual(
            usage.remaining_generations,
            PRO_PLAN.monthly_generation_limit - FREE_PLAN.monthly_generation_limit,
        )
        self.assertTrue(usage.can_create_generation)


if __name__ == "__main__":
    unittest.main()
