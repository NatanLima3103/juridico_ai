import unittest
from urllib.parse import unquote

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import SECRET_KEY, SESSION_COOKIE_NAME, STATIC_DIR
from app.database import Base, get_db
from app.models.writing_profile import WritingProfile
from app.routers import auth, writing_profiles
from app.schemas.user import UserCreate
from app.services.plan_service import FREE_PLAN, PRO_PLAN
from app.services.user_service import criar_usuario
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


def authenticate_test_client(client: TestClient, testing_session_local: sessionmaker, *, email: str = "maria@example.com") -> None:
    response = client.post(
        "/auth/login",
        data={
            "email": email,
            "password": "senha1234",
            "next": "/writing-profiles",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def create_profile_record(db, *, user_id: int, name: str = "Perfil existente") -> WritingProfile:
    perfil = WritingProfile(
        user_id=user_id,
        profile_name=name,
        tone="Formal",
    )
    db.add(perfil)
    return perfil


class WritingProfilesTests(unittest.TestCase):
    def test_create_profile_persists_record_and_favorite_flag(self):
        client, testing_session_local = create_writing_profiles_test_client()
        create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        authenticate_test_client(client, testing_session_local)

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
            perfil = buscar_perfil_por_id(db, 1, 1)
            self.assertIsNotNone(perfil)
            self.assertEqual(perfil.profile_name, "Civel Formal")
            self.assertTrue(perfil.is_favorite)
            self.assertEqual(perfil.status, "ativo")
            self.assertEqual(perfil.user_id, 1)
        finally:
            db.close()

    def test_list_page_renders_saved_profile(self):
        client, testing_session_local = create_writing_profiles_test_client()
        create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        authenticate_test_client(client, testing_session_local)

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

    def test_list_page_hides_profiles_from_other_users(self):
        client, testing_session_local = create_writing_profiles_test_client()
        usuario_1 = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        usuario_2 = create_user_for_test(testing_session_local, full_name="Ana Souza", email="ana@example.com")

        db = testing_session_local()
        try:
            db.add(
                WritingProfile(
                    user_id=usuario_1.id,
                    profile_name="Perfil Maria",
                    tone="Formal",
                )
            )
            db.add(
                WritingProfile(
                    user_id=usuario_2.id,
                    profile_name="Perfil Ana",
                    tone="Objetivo",
                )
            )
            db.commit()
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.get("/writing-profiles")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Perfil Maria", response.text)
        self.assertNotIn("Perfil Ana", response.text)

    def test_edit_page_blocks_profile_from_other_user(self):
        client, testing_session_local = create_writing_profiles_test_client()
        create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")
        usuario_2 = create_user_for_test(testing_session_local, full_name="Ana Souza", email="ana@example.com")

        db = testing_session_local()
        try:
            perfil = WritingProfile(
                user_id=usuario_2.id,
                profile_name="Perfil Ana",
                tone="Objetivo",
            )
            db.add(perfil)
            db.commit()
            db.refresh(perfil)
            perfil_id = perfil.id
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.get(f"/writing-profiles/{perfil_id}/edit", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(unquote(response.headers["location"]), "/writing-profiles?erro=Perfil não encontrado.")

    def test_free_plan_blocks_profile_creation_when_limit_is_reached(self):
        client, testing_session_local = create_writing_profiles_test_client()
        usuario = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")

        db = testing_session_local()
        try:
            for index in range(FREE_PLAN.writing_profile_limit):
                create_profile_record(db, user_id=usuario.id, name=f"Perfil Free {index}")
            db.commit()
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.post(
            "/writing-profiles/create",
            data={
                "profile_name": "Novo Perfil Free",
                "tone": "Formal",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Plano gratuito", response.text)
        self.assertIn("limite", response.text.lower())

    def test_pro_plan_can_create_profile_after_free_limit(self):
        client, testing_session_local = create_writing_profiles_test_client()
        usuario = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")

        db = testing_session_local()
        try:
            usuario_db = db.merge(usuario)
            usuario_db.plan_slug = "pro"
            for index in range(FREE_PLAN.writing_profile_limit):
                create_profile_record(db, user_id=usuario_db.id, name=f"Perfil Pro {index}")
            db.commit()
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.post(
            "/writing-profiles/create",
            data={
                "profile_name": "Novo Perfil Pro",
                "tone": "Objetivo",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/writing-profiles?sucesso=Perfil%20criado%20com%20sucesso.")

    def test_pro_plan_blocks_profile_creation_when_its_limit_is_reached(self):
        client, testing_session_local = create_writing_profiles_test_client()
        usuario = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")

        db = testing_session_local()
        try:
            usuario_db = db.merge(usuario)
            usuario_db.plan_slug = "pro"
            for index in range(PRO_PLAN.writing_profile_limit):
                create_profile_record(db, user_id=usuario_db.id, name=f"Perfil Pro {index}")
            db.commit()
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.post(
            "/writing-profiles/create",
            data={
                "profile_name": "Perfil Excedente",
                "tone": "Tecnico",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Plano Pro", response.text)
        self.assertIn(str(PRO_PLAN.writing_profile_limit), response.text)

    def test_free_plan_blocks_profile_duplication_when_limit_is_reached(self):
        client, testing_session_local = create_writing_profiles_test_client()
        usuario = create_user_for_test(testing_session_local, full_name="Maria Silva", email="maria@example.com")

        db = testing_session_local()
        try:
            perfil = create_profile_record(db, user_id=usuario.id, name="Perfil Original")
            db.commit()
            db.refresh(perfil)
            perfil_id = perfil.id
        finally:
            db.close()

        authenticate_test_client(client, testing_session_local)

        response = client.post(f"/writing-profiles/{perfil_id}/duplicate", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("/writing-profiles?erro=", response.headers["location"])
        self.assertIn("Plano%20gratuito", response.headers["location"])


if __name__ == "__main__":
    unittest.main()
