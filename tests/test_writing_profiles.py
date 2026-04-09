import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import Base, get_db
from app.routers import writing_profiles
from app.services.writing_profile_service import buscar_perfil_por_id


def create_writing_profiles_test_client() -> tuple[TestClient, sessionmaker]:
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
    app.include_router(writing_profiles.router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


class WritingProfilesTests(unittest.TestCase):
    def test_create_profile_persists_record_and_favorite_flag(self):
        client, testing_session_local = create_writing_profiles_test_client()

        response = client.post(
            "/writing-profiles/create",
            data={
                "profile_name": "Civel Formal",
                "tone": "Formal",
                "lawyer_name": "Maria Silva",
                "office_name": "Silva Advogados",
                "qualification_style": "Ja qualificada nos autos",
                "opening_phrase": "Vem respeitosamente",
                "request_intro": "Diante do exposto, requer",
                "closing_phrase": "Pede deferimento",
                "legal_style_notes": "Linguagem tecnica",
                "recurring_expressions": "data venia",
                "tags": "civel",
                "status": "ativo",
                "is_favorite": "true",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/writing-profiles?sucesso=Perfil%20criado%20com%20sucesso.")

        db = testing_session_local()
        try:
            perfil = buscar_perfil_por_id(db, 1)
            self.assertIsNotNone(perfil)
            self.assertEqual(perfil.profile_name, "Civel Formal")
            self.assertTrue(perfil.is_favorite)
            self.assertEqual(perfil.status, "ativo")
        finally:
            db.close()

    def test_list_page_renders_saved_profile(self):
        client, _ = create_writing_profiles_test_client()

        create_response = client.post(
            "/writing-profiles/create",
            data={
                "profile_name": "Trabalhista Objetivo",
                "tone": "Objetivo",
            },
            follow_redirects=False,
        )

        self.assertEqual(create_response.status_code, 303)

        list_response = client.get("/writing-profiles")

        self.assertEqual(list_response.status_code, 200)
        self.assertIn("1 resultado(s)", list_response.text)
        self.assertIn("Trabalhista Objetivo", list_response.text)
        self.assertNotIn("Nenhum perfil encontrado", list_response.text)


if __name__ == "__main__":
    unittest.main()
