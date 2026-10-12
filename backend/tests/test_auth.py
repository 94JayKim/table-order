from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.factory import create_app


def make(ttl=180):
    s = Settings(database_url="sqlite:///:memory:", login_ttl_seconds=ttl, kakao_rest_api_key="",
                 public_base_url="http://t", jwt_secret="x" * 32, _env_file=None)
    return create_app(s)


def scan_and_login(c, token, nick="홍길동"):
    r = c.get(f"/api/auth/kakao/start?token={token}", follow_redirects=False)
    assert r.status_code == 302 and "/kakao/mock" in r.headers["location"]
    return c.get("/api/auth/kakao/callback", params={"state": token, "code": f"mock-{nick}"})


def test_full_flow_with_websocket():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 12}).json()
        assert q["qr_url"] == f"http://t/api/auth/kakao/start?token={q['token']}" and q["expires_in"] == 180
        with c.websocket_connect(f"/api/auth/ws/{q['secret']}") as ws:
            assert ws.receive_json()["status"] == "waiting"
            c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False)
            assert ws.receive_json() == {"event": "scanned"}
            r = c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-홍길동"})
            assert r.status_code == 200 and "홍길동" in r.text
            done = ws.receive_json()
        assert done["event"] == "logged_in" and done["member"]["nickname"] == "홍길동"
        me = c.get("/api/members/me", headers={"Authorization": f"Bearer {done['access_token']}"})
        assert me.status_code == 200 and me.json()["visit_count"] == 1


def test_token_is_single_use_and_rescan_rejected():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        assert scan_and_login(c, q["token"]).status_code == 200
        assert c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False).status_code == 410
        again = c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-다른사람"})
        assert again.status_code == 410


def test_callback_requires_scan_and_valid_state():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        # 스캔 없이 콜백, 알 수 없는 state 모두 거부
        assert c.get("/api/auth/kakao/callback", params={"state": q["token"], "code": "mock-a"}).status_code == 410
        assert c.get("/api/auth/kakao/callback", params={"state": "nope", "code": "mock-a"}).status_code == 410
        assert c.get("/api/auth/kakao/start?token=nope", follow_redirects=False).status_code == 404


def test_secret_is_separate_from_qr_token():
    with TestClient(make()) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        scan_and_login(c, q["token"])
        assert c.get(f"/api/auth/qr/{q['token']}").status_code == 404  # QR 값으로는 결과를 못 본다
        first = c.get(f"/api/auth/qr/{q['secret']}").json()
        assert first["event"] == "logged_in" and first["access_token"]
        assert c.get(f"/api/auth/qr/{q['secret']}").json()["status"] == "claimed"  # 한 번만 전달


def test_expiry_over_websocket_and_polling():
    with TestClient(make(ttl=1)) as c:
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        with c.websocket_connect(f"/api/auth/ws/{q['secret']}") as ws:
            ws.receive_json()
            assert ws.receive_json() == {"event": "expired"}
        assert c.get(f"/api/auth/qr/{q['secret']}").json()["status"] == "expired"
        assert c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False).status_code == 410


def test_unknown_websocket_secret_rejected():
    with TestClient(make()) as c:
        with pytest.raises(Exception):
            with c.websocket_connect("/api/auth/ws/nope"):
                pass


def test_returning_member_and_profile_update():
    with TestClient(make()) as c:
        tokens = []
        for _ in range(2):
            q = c.post("/api/auth/qr", json={"table_no": 1}).json()
            scan_and_login(c, q["token"], "단골")
            tokens.append(c.get(f"/api/auth/qr/{q['secret']}").json()["access_token"])
        h = {"Authorization": f"Bearer {tokens[1]}"}
        assert c.get("/api/members/me", headers=h).json()["visit_count"] == 2
        r = c.patch("/api/members/me", headers=h, json={"phone": "010-1234-5678", "marketing_consent": True})
        assert r.json()["phone"] == "010-1234-5678" and r.json()["marketing_consent"] is True
        assert c.patch("/api/members/me", headers=h, json={"phone": "123"}).status_code == 422
        assert c.get("/api/members/me").status_code == 401
        assert c.get("/api/members/me", headers={"Authorization": "Bearer bad"}).status_code == 401


def test_mock_page_hidden_when_real_keys_set():
    s = Settings(database_url="sqlite:///:memory:", kakao_rest_api_key="k", _env_file=None)
    with TestClient(create_app(s)) as c:
        assert c.get("/api/auth/kakao/mock?state=x").status_code == 404
        q = c.post("/api/auth/qr", json={"table_no": 1}).json()
        loc = c.get(f"/api/auth/kakao/start?token={q['token']}", follow_redirects=False).headers["location"]
        qs = parse_qs(urlparse(loc).query)
        assert loc.startswith("https://kauth.kakao.com/oauth/authorize") and qs["state"] == [q["token"]]
