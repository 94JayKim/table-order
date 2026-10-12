from fastapi.testclient import TestClient

from app.factory import create_app


def test_health():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}


def test_admin_requires_token():
    assert TestClient(create_app()).get("/admin/api/orders").status_code == 401
