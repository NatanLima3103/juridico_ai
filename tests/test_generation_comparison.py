import sys
import types
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
from app.services import ai_generation_service
from app.services.generation_service import gerar_rascunho_juridico_com_metadata
from app.services.user_service import criar_usuario


class CapturingResponsesClient:
    def __init__(self, *, text: str, response_id: str, calls: list[dict]):
        self._text = text
        self._response_id = response_id
        self._calls = calls

    def create(self, **kwargs):
        self._calls.append(kwargs)
        return types.SimpleNamespace(output_text=self._text, id=self._response_id)


class CapturingOpenAIClient:
    def __init__(self, *, text: str, response_id: str, calls: list[dict]):
        self.responses = CapturingResponsesClient(text=text, response_id=response_id, calls=calls)


def build_fake_openai_module(*, text: str, response_id: str, calls: list[dict]):
    return types.SimpleNamespace(
        OpenAI=lambda api_key=None: CapturingOpenAIClient(
            text=text,
            response_id=response_id,
            calls=calls,
        )
    )


def create_generation_comparison_client() -> tuple[TestClient, sessionmaker]:
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


def criar_usuario_comparacao(testing_session_local: sessionmaker):
    db = testing_session_local()
    try:
        return criar_usuario(
            db,
            UserCreate(
                full_name="Cliente Comparacao",
                email="comparacao@example.com",
                password="senha1234",
            ),
        )
    finally:
        db.close()


def autenticar(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        data={
            "email": "comparacao@example.com",
            "password": "senha1234",
            "next": "/generations",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


class GenerationComparisonTests(unittest.TestCase):
    def test_same_case_can_be_generated_by_rule_or_ai_with_distinct_metadata(self):
        payload = {
            "client_name": "Cliente Teste",
            "document_type": "Contestacao",
            "case_subject": "Cobranca indevida",
            "facts": "A parte re impugna a existencia do debito e aponta falha documental da autora.",
            "requests": "Improcedencia dos pedidos e condenacao em honorarios.",
            "legal_basis": "CPC e Codigo Civil.",
            "context_used": "[RESUMO DO CASO]\nContestacao por cobranca indevida.",
            "writing_profile": None,
            "documentos_selecionados": [],
        }

        with patch.object(ai_generation_service, "OPENAI_API_KEY", ""):
            rule_result = gerar_rascunho_juridico_com_metadata(**payload)

        calls: list[dict] = []
        fake_openai = build_fake_openai_module(
            text="Texto IA comparativo para contestacao por cobranca indevida.",
            response_id="resp_comparativo",
            calls=calls,
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", "test-key"):
            with patch.dict(sys.modules, {"openai": fake_openai}):
                ai_result = gerar_rascunho_juridico_com_metadata(**payload)

        self.assertEqual(rule_result.generation_strategy, "rule_based")
        self.assertIsNone(rule_result.llm_provider)
        self.assertIn("CONTESTACAO", rule_result.text.upper())
        self.assertIn("A linha defensiva deve guardar correspondencia", rule_result.text)

        self.assertEqual(ai_result.text, "Texto IA comparativo para contestacao por cobranca indevida.")
        self.assertEqual(ai_result.generation_strategy, "ai_openai")
        self.assertEqual(ai_result.llm_provider, "openai")
        self.assertEqual(ai_result.llm_response_id, "resp_comparativo")
        self.assertIsNone(ai_result.llm_error)

        self.assertEqual(len(calls), 1)
        self.assertIn("Contestacao", calls[0]["input"])
        self.assertIn("Cobranca indevida", calls[0]["input"])
        self.assertIn("[MATRIZ DE COERENCIA JURIDICA]", calls[0]["input"])

    def test_ai_generation_metadata_is_persisted_when_creating_generation(self):
        client, testing_session_local = create_generation_comparison_client()
        usuario = criar_usuario_comparacao(testing_session_local)
        autenticar(client)

        calls: list[dict] = []
        fake_openai = build_fake_openai_module(
            text="Texto IA persistido com metadados comparativos.",
            response_id="resp_persistido",
            calls=calls,
        )

        with patch.object(ai_generation_service, "OPENAI_API_KEY", "test-key"):
            with patch.dict(sys.modules, {"openai": fake_openai}):
                response = client.post(
                    "/generations/create",
                    data={
                        "client_name": "Cliente Teste",
                        "document_type": "Contrato",
                        "case_subject": "Viabilidade de rescisao contratual",
                        "facts": "A consulente pretende avaliar riscos de ruptura antecipada.",
                        "requests": "Analise de viabilidade e recomendacao pratica.",
                        "legal_basis": "Codigo Civil e boa-fe objetiva.",
                    },
                    follow_redirects=False,
                )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(len(calls), 1)

        db = testing_session_local()
        try:
            geracao = db.query(Generation).filter(Generation.user_id == usuario.id).first()
            self.assertIsNotNone(geracao)
            self.assertEqual(geracao.generated_text, "Texto IA persistido com metadados comparativos.")
            self.assertEqual(geracao.generation_strategy, "ai_openai")
            self.assertEqual(geracao.llm_provider, "openai")
            self.assertEqual(geracao.llm_model, ai_generation_service.OPENAI_MODEL)
            self.assertEqual(geracao.llm_response_id, "resp_persistido")
            self.assertIsNone(geracao.llm_error)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
