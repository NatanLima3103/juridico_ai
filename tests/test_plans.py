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
from app.routers import auth, plans
from app.schemas.user import UserCreate
from app.services.user_service import criar_usuario


def create_plans_test_client() -> tuple[TestClient, sessionmaker]:
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
    app.include_router(plans.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


def criar_usuario_tela_planos(testing_session_local: sessionmaker, *, plan_slug: str = "free"):
    db = testing_session_local()
    try:
        usuario = criar_usuario(
            db,
            UserCreate(
                full_name="Usuario Tela Planos",
                email="plans@example.com",
                password="senha1234",
            ),
        )
        usuario_db = db.merge(usuario)
        usuario_db.plan_slug = plan_slug
        db.commit()
        db.refresh(usuario_db)
        return usuario_db
    finally:
        db.close()


def autenticar(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={
            "email": "plans@example.com",
            "password": "senha1234",
            "next": "/plans",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


class PlansScreenTests(unittest.TestCase):
    def test_plans_screen_renders_current_plan_and_available_options(self):
        client, testing_session_local = create_plans_test_client()
        criar_usuario_tela_planos(testing_session_local)
        autenticar(client)

        response = client.get("/plans")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Seu plano", response.text)
        self.assertIn("Plano gratuito", response.text)
        self.assertIn("Plano Pro", response.text)
        self.assertIn("<strong>10</strong>", response.text)
        self.assertIn("<strong>5</strong>", response.text)
        self.assertIn("<strong>25</strong>", response.text)
        self.assertIn("Gerações", response.text)
        self.assertIn("Perfis", response.text)
        self.assertIn("Atual", response.text)

    def test_checkout_without_payment_url_shows_configuration_message(self):
        client, testing_session_local = create_plans_test_client()
        criar_usuario_tela_planos(testing_session_local)
        autenticar(client)

        response = client.post("/plans/checkout", data={"plan_slug": "pro"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("Checkout de pagamento ainda nao configurado", response.text)

    def test_checkout_redirects_to_configured_payment_url(self):
        client, testing_session_local = create_plans_test_client()
        criar_usuario_tela_planos(testing_session_local)
        autenticar(client)

        with patch("app.core.config.PAYMENT_CHECKOUT_URL", "https://pay.example/checkout"):
            response = client.post(
                "/plans/checkout",
                data={"plan_slug": "pro"},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["location"].startswith("https://pay.example/checkout?"))
        self.assertIn("plan_slug=pro", response.headers["location"])
        self.assertIn("success_url=", response.headers["location"])

    def test_checkout_rejects_current_plan(self):
        client, testing_session_local = create_plans_test_client()
        criar_usuario_tela_planos(testing_session_local, plan_slug="pro")
        autenticar(client)

        response = client.post("/plans/checkout", data={"plan_slug": "pro"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Este plano ja esta ativo", response.text)


if __name__ == "__main__":
    unittest.main()
