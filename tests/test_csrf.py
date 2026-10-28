import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.csrf import OriginCheckMiddleware
from app.main import app as main_app
from app.routers import plans


def create_csrf_test_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(OriginCheckMiddleware, exempt_paths={"/webhook"})

    @app.post("/acao")
    def acao():
        return {"ok": True}

    @app.get("/acao")
    def acao_get():
        return {"ok": True}

    @app.post("/webhook")
    def webhook():
        return {"ok": True}

    return TestClient(app, base_url="http://juridico.example")


class OriginCheckMiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.client = create_csrf_test_client()

    def test_allows_same_origin_requests(self):
        casos = [
            {"Sec-Fetch-Site": "same-origin"},
            {"Sec-Fetch-Site": "none"},
            {"Origin": "https://juridico.example"},
            {"Origin": "http://juridico.example:8080"},
            {"Referer": "https://juridico.example/documents"},
            {},
        ]
        for headers in casos:
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post("/acao", headers=headers).status_code, 200)

    def test_blocks_cross_site_requests(self):
        casos = [
            {"Sec-Fetch-Site": "cross-site"},
            {"Sec-Fetch-Site": "same-site"},
            {"Sec-Fetch-Site": "cross-site", "Origin": "https://juridico.example"},
            {"Origin": "https://atacante.example"},
            {"Origin": "null"},
            {"Referer": "https://atacante.example/pagina"},
        ]
        for headers in casos:
            with self.subTest(headers=headers):
                self.assertEqual(self.client.post("/acao", headers=headers).status_code, 403)

    def test_safe_methods_and_exempt_paths_are_not_checked(self):
        headers = {"Sec-Fetch-Site": "cross-site", "Origin": "https://atacante.example"}
        self.assertEqual(self.client.get("/acao", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/webhook", headers=headers).status_code, 200)

    def test_main_app_uses_middleware_and_exempts_payment_webhook(self):
        middlewares = [m for m in main_app.user_middleware if m.cls is OriginCheckMiddleware]
        self.assertEqual(len(middlewares), 1)
        self.assertIn(plans.PAYMENT_WEBHOOK_PATH, middlewares[0].kwargs["exempt_paths"])


if __name__ == "__main__":
    unittest.main()
