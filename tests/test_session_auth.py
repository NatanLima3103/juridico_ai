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
from app.routers import auth, home, writing_profiles
from app.schemas.user import UserCreate
from app.services.user_service import criar_usuario


def create_session_auth_test_client() -> tuple[TestClient, sessionmaker]:
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
    app.include_router(home.router)
    app.include_router(auth.router)
    app.include_router(writing_profiles.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


class SessionAuthTests(unittest.TestCase):
    def test_protected_route_redirects_to_login_with_next(self):
        client, _ = create_session_auth_test_client()

        response = client.get("/writing-profiles", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(
            response.headers["location"],
            "/auth/login?next=%2Fwriting-profiles&erro=Fa%C3%A7a%20login%20para%20continuar.",
        )

    def test_login_redirects_to_original_destination(self):
        client, testing_session_local = create_session_auth_test_client()

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

        response = client.post(
            "/auth/login",
            data={
                "email": "ana@example.com",
                "password": "senha1234",
                "next": "/writing-profiles",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/writing-profiles")

    def test_authenticated_user_cannot_open_login_form_again(self):
        client, testing_session_local = create_session_auth_test_client()

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

        login_response = client.post(
            "/auth/login",
            data={
                "email": "ana@example.com",
                "password": "senha1234",
                "next": "/",
            },
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

        form_response = client.get("/auth/login", follow_redirects=False)

        self.assertEqual(form_response.status_code, 303)
        self.assertEqual(form_response.headers["location"], "/")


if __name__ == "__main__":
    unittest.main()
