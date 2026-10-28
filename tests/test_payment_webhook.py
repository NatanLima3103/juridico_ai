import json
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.routers import plans
from app.schemas.user import UserCreate
from app.services.payment_service import assinar_webhook
from app.services.user_service import criar_usuario

SEGREDO = "segredo-de-teste"


def create_webhook_test_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(plans.webhook_router)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), testing_session_local


class PaymentWebhookTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("app.core.config.PAYMENT_WEBHOOK_SECRET", SEGREDO)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client, self.testing_session_local = create_webhook_test_client()
        db = self.testing_session_local()
        try:
            self.user_id = criar_usuario(
                db,
                UserCreate(full_name="Ana Souza", email="ana@example.com", password="senha1234"),
            ).id
        finally:
            db.close()

    def _enviar(self, payload: dict, *, timestamp: int | None = None, secret: str = SEGREDO):
        body = json.dumps(payload).encode("utf-8")
        ts = str(timestamp if timestamp is not None else int(time.time()))
        return self.client.post(
            plans.PAYMENT_WEBHOOK_PATH,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Payment-Timestamp": ts,
                "X-Payment-Signature": assinar_webhook(ts, body, secret),
            },
        )

    def _plano_atual(self) -> str:
        db = self.testing_session_local()
        try:
            return db.query(User).filter(User.id == self.user_id).one().plan_slug
        finally:
            db.close()

    def test_activation_and_cancellation_update_plan(self):
        ativacao = {"event_id": "evt_1", "event": "subscription.activated", "user_id": self.user_id, "plan_slug": "pro"}

        response = self._enviar(ativacao)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._plano_atual(), "pro")

        # Reenvio do mesmo evento nao muda nada nem quebra.
        response = self._enviar(ativacao)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._plano_atual(), "pro")

        response = self._enviar(
            {"event_id": "evt_2", "event": "subscription.canceled", "user_id": self.user_id, "plan_slug": "pro"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._plano_atual(), "free")

        db = self.testing_session_local()
        try:
            acoes = [acao for (acao,) in db.query(AuditLog.action).order_by(AuditLog.id).all()]
        finally:
            db.close()
        self.assertEqual(acoes.count("plan_changed_by_payment"), 2)
        self.assertIn("plan_payment_event_ignored", acoes)

    def test_rejects_invalid_signature(self):
        response = self._enviar(
            {"event": "subscription.activated", "user_id": self.user_id},
            secret="segredo-errado",
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self._plano_atual(), "free")

    def test_rejects_missing_signature(self):
        response = self.client.post(
            plans.PAYMENT_WEBHOOK_PATH,
            json={"event": "subscription.activated", "user_id": self.user_id},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self._plano_atual(), "free")

    def test_rejects_old_timestamp(self):
        response = self._enviar(
            {"event": "subscription.activated", "user_id": self.user_id},
            timestamp=int(time.time()) - 3600,
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self._plano_atual(), "free")

    def test_rejects_unknown_event_plan_and_user(self):
        casos = [
            ({"event": "subscription.paused", "user_id": self.user_id}, 400),
            ({"event": "subscription.activated", "user_id": self.user_id, "plan_slug": "free"}, 400),
            ({"event": "subscription.activated", "user_id": "abc"}, 400),
            ({"event": "subscription.activated", "user_id": 9999}, 404),
        ]
        for payload, status_code in casos:
            with self.subTest(payload=payload):
                self.assertEqual(self._enviar(payload).status_code, status_code)
        self.assertEqual(self._plano_atual(), "free")

    def test_returns_503_when_secret_not_configured(self):
        with patch("app.core.config.PAYMENT_WEBHOOK_SECRET", ""):
            response = self._enviar({"event": "subscription.activated", "user_id": self.user_id}, secret="x")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
