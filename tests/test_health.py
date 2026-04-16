from fastapi.testclient import TestClient

from app.main import app


def test_health_check_responde_status_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_check_devolve_request_id():
    client = TestClient(app)

    response = client.get("/health", headers={"X-Request-ID": "req-teste"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-teste"
