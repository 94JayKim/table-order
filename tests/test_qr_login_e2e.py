"""user 페이지(Streamlit AppTest) ↔ 실제 백엔드(FastAPI TestClient) QR 로그인 통합 테스트.

휴대폰 동작은 같은 TestClient 로 흉내 낸다 (QR 주소 열기 → 모의 카카오 로그인 콜백).
실행: 저장소 루트에서 `python -m pytest tests -q` (fastapi, streamlit 필요)
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "user")]

import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.core.settings import Settings
from app.factory import create_app
from shared import api

APP = str(ROOT / "user" / "app.py")


@pytest.fixture
def server():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="", public_base_url="http://t",
                 jwt_secret="x" * 32, admin_token="admin-secret", _env_file=None)
    with TestClient(create_app(s)) as c:
        api.set_client(c)
        yield c
    api.set_client(None)


def phone_login(server, qr_url: str, nickname: str):
    """휴대폰이 QR을 스캔하고 (모의) 카카오 로그인을 마치는 과정."""
    path = urlparse(qr_url)
    r = server.get(f"{path.path}?{path.query}", follow_redirects=False)
    assert r.status_code == 302
    state = path.query.removeprefix("token=")
    assert server.get("/api/auth/kakao/callback", params={"state": state, "code": f"mock-{nickname}"}).status_code == 200


def test_qr_scan_changes_tablet_screen_and_profile_saves(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    login = app.session_state["login"]
    assert login and login["qr_url"].startswith("http://t/api/auth/kakao/start?token=")
    assert not app.session_state["member"] and any("스캔해 주세요" in c.value for c in app.caption)

    phone_login(server, login["qr_url"], "홍대손님")  # 휴대폰에서 스캔 + 로그인
    app.run()  # 태블릿의 폴링이 로그인 완료를 감지
    assert app.session_state["member"]["nickname"] == "홍대손님"
    assert app.session_state["access_token"] and app.session_state["login"] is None
    assert any("로그인 완료" in m.value for m in app.markdown) or any("로그인 완료" in str(e.value) for e in app.get("html"))

    app.text_input[0].set_value("010-1234-5678")
    app.checkbox[0].check()
    next(b for b in app.get("button") if b.proto.label == "저장").click().run()
    me = server.get("/api/members/me", headers={"Authorization": f"Bearer {app.session_state['access_token']}"}).json()
    assert me["phone"] == "010-1234-5678" and me["marketing_consent"] is True
    assert not app.exception


def test_used_qr_is_rejected_and_new_qr_issued_on_refresh(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    first = app.session_state["login"]
    phone_login(server, first["qr_url"], "가")
    path = urlparse(first["qr_url"])
    assert server.get(f"{path.path}?{path.query}", follow_redirects=False).status_code == 410  # 재사용 불가
    app.run()
    assert app.session_state["member"]["nickname"] == "가"


def test_expired_qr_can_be_refreshed(server):
    app = AppTest.from_file(APP, default_timeout=30).run()
    old = app.session_state["login"]["token"]
    app.session_state["login"]["created"] -= 10_000  # 만료시키기
    app.run()
    next(b for b in app.get("button") if b.proto.label == "QR 새로고침").click().run()
    assert app.session_state["login"]["token"] != old


def test_page_works_without_server_and_table_comes_from_url():
    api.set_client(__import__("httpx").Client(base_url="http://127.0.0.1:9", timeout=1))
    try:
        app = AppTest.from_file(APP, default_timeout=30)
        app.query_params["table"] = "7"
        app.run()
        assert not app.exception and app.session_state["login"] is None and app.session_state["table"] == 7
        assert any("QR 로그인을 사용할 수 없어요" in c.value for c in app.caption)
        app.button(key="start_btn").click().run()  # 서버 없이도 주문 화면 진입
        assert not app.exception
    finally:
        api.set_client(None)
