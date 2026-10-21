from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_responde():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == "ok"
    assert body["database"]["status"] in {"ok", "error"}


def test_openapi_disponible():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/health" in r.json()["paths"]
