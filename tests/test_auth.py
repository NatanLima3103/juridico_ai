import unittest
from pathlib import Path

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
from app.routers import auth


def create_auth_test_client(tmp_path: Path) -> TestClient:
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
    app.include_router(auth.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def create_auth_test_client_with_session() -> tuple[TestClient, sessionmaker]:
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


class AuthLogoutTests(unittest.TestCase):
    def test_logout_clears_active_session_cookie(self):
        client = create_auth_test_client(Path("."))

        register_response = client.post(
            "/auth/register",
            data={
                "full_name": "Maria Silva",
                "email": "maria@example.com",
                "password": "senha1234",
                "confirm_password": "senha1234",
            },
            follow_redirects=False,
        )
        self.assertEqual(register_response.status_code, 303)

        login_response = client.post(
            "/auth/login",
            data={
                "email": "maria@example.com",
                "password": "senha1234",
            },
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)
        self.assertIn(SESSION_COOKIE_NAME, client.cookies)

        logout_response = client.post("/auth/logout", follow_redirects=False)

        self.assertEqual(logout_response.status_code, 303)
        self.assertEqual(
            logout_response.headers["location"],
            "/auth/login?sucesso=Sess%C3%A3o+encerrada+com+sucesso.",
        )
        self.assertIn("Max-Age=0", logout_response.headers["set-cookie"])
        self.assertNotIn(SESSION_COOKIE_NAME, client.cookies)

    def test_logout_without_active_session_still_redirects(self):
        client = create_auth_test_client(Path("."))

        logout_response = client.post("/auth/logout", follow_redirects=False)

        self.assertEqual(logout_response.status_code, 303)
        self.assertEqual(
            logout_response.headers["location"],
            "/auth/login?sucesso=Sess%C3%A3o+encerrada+com+sucesso.",
        )
        self.assertIn("Max-Age=0", logout_response.headers["set-cookie"])

    def test_auth_actions_are_written_to_audit_log(self):
        client, testing_session_local = create_auth_test_client_with_session()

        register_response = client.post(
            "/auth/register",
            data={
                "full_name": "Maria Silva",
                "email": "maria@example.com",
                "password": "senha1234",
                "confirm_password": "senha1234",
            },
            follow_redirects=False,
        )
        self.assertEqual(register_response.status_code, 303)

        failed_login_response = client.post(
            "/auth/login",
            data={
                "email": "maria@example.com",
                "password": "senha-errada",
            },
            follow_redirects=False,
        )
        self.assertEqual(failed_login_response.status_code, 400)

        login_response = client.post(
            "/auth/login",
            data={
                "email": "maria@example.com",
                "password": "senha1234",
            },
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

        logout_response = client.post("/auth/logout", follow_redirects=False)
        self.assertEqual(logout_response.status_code, 303)

        db = testing_session_local()
        try:
            acoes = [acao for (acao,) in db.query(AuditLog.action).order_by(AuditLog.id.asc()).all()]
            self.assertIn("user_register", acoes)
            self.assertIn("login_failed", acoes)
            self.assertIn("login_success", acoes)
            self.assertIn("logout", acoes)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
