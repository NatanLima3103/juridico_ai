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


if __name__ == "__main__":
    unittest.main()
