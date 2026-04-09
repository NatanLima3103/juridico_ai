import re
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
from app.routers import auth
from app.schemas.user import UserCreate
from app.services.user_service import autenticar_usuario, criar_usuario


def create_password_reset_test_client() -> tuple[TestClient, sessionmaker]:
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

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


class PasswordResetTests(unittest.TestCase):
    def test_password_reset_updates_user_password(self):
        client, testing_session_local = create_password_reset_test_client()

        db = testing_session_local()
        try:
            criar_usuario(
                db,
                UserCreate(
                    full_name="Ana Souza",
                    email="ana@example.com",
                    password="senha1234",
                ),
            )
        finally:
            db.close()

        forgot_response = client.post(
            "/auth/forgot-password",
            data={"email": "ana@example.com"},
        )

        self.assertEqual(forgot_response.status_code, 200)
        self.assertIn("link de recuperação foi gerado", forgot_response.text)

        token_match = re.search(r"/auth/reset-password/([A-Za-z0-9._\-]+)", forgot_response.text)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)

        reset_response = client.post(
            f"/auth/reset-password/{token}",
            data={
                "password": "novaSenha123",
                "confirm_password": "novaSenha123",
            },
            follow_redirects=False,
        )

        self.assertEqual(reset_response.status_code, 303)
        self.assertIn("/auth/login?sucesso=", reset_response.headers["location"])

        db = testing_session_local()
        try:
            self.assertIsNone(autenticar_usuario(db, email="ana@example.com", password="senha1234"))
            self.assertIsNotNone(autenticar_usuario(db, email="ana@example.com", password="novaSenha123"))
        finally:
            db.close()

    def test_invalid_token_shows_error(self):
        client, _ = create_password_reset_test_client()

        response = client.get("/auth/reset-password/token-invalido")

        self.assertEqual(response.status_code, 400)
        self.assertIn("inválido ou expirou", response.text)


if __name__ == "__main__":
    unittest.main()
