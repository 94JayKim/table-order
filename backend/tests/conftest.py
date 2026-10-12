from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.factory import create_app
from app.services.grades import KST

ADMIN = {"Authorization": "Bearer admin-secret"}


def settings(**kw) -> Settings:
    base = dict(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None)
    return Settings(**{**base, **kw})


def login(c: TestClient, nickname: str) -> dict:
    """모의 카카오 로그인으로 회원을 만들고 JWT 헤더를 돌려준다."""
    q = c.post("/api/auth/qr", json={"table_no": 1}).json()
    c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False)
    c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": f"mock-{nickname}"})
    return {"Authorization": f"Bearer {c.get(f'/api/auth/qr/{q['secret']}').json()['access_token']}"}


@pytest.fixture
def client():
    with TestClient(create_app(settings())) as c:
        yield c


def at(hour: int, minute: int = 0):
    return lambda: datetime(2026, 10, 12, hour, minute, tzinfo=KST)
