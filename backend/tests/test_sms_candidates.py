"""AI 문자 후보(POST /marketing/sms/candidates)와 외부 정보(GET /marketing/external-context) 테스트."""

import httpx
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services.external_info import EVENT_URL
from tests.conftest import ADMIN, at, login, set_profile, settings

CANDIDATES = "/admin/api/marketing/sms/candidates"
EXTERNAL = "/admin/api/marketing/external-context"


def member(c, nick, consent=True):
    h = login(c, nick, agree=consent)
    set_profile(c, h, phone="010-1234-5678")


def fake_external(c, weather="맑은 18도 날씨", event=""):
    """외부 API 호출 대신 정해 둔 값을 돌려주고, 몇 번 불렸는지 센다."""
    calls = {"n": 0}

    def fetch_weather():
        calls["n"] += 1
        return weather
    c.app.state.external.fetch_weather = fetch_weather
    c.app.state.external.fetch_events = lambda day: event
    return calls


def test_candidates_without_ai_key_are_templates():
    with TestClient(create_app(settings(gemini_api_key=""), sms_clock=at(14))) as c:
        fake_external(c)
        member(c, "가")  # 방문 1회 → 신규 등급, 수신 동의
        cands = c.post(CANDIDATES, headers=ADMIN).json()
        assert 1 <= len(cands) <= 5
        assert all(x["source"] == "template" and x["body"] and x["grades"] for x in cands)
        # 신규 회원만 있으므로 휴면·단골만 받는 조합은 빠진다
        assert not [x for x in cands if x["keywords"] in (["휴면"], ["단골"])]
        weather = [x for x in cands if x["keywords"] == ["날씨", "주문"]][0]
        assert "맑은 18도 날씨" in weather["body"]


def test_candidates_empty_when_no_sendable_member():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        fake_external(c)
        member(c, "가", consent=False)  # 수신 동의 안 함
        assert c.post(CANDIDATES, headers=ADMIN).json() == []


def test_candidates_use_ai_text_and_fall_back_on_error():
    with TestClient(create_app(settings(gemini_api_key="k"), sms_clock=at(14))) as c:
        fake_external(c)
        member(c, "가")
        c.app.state.sms_candidates._ask_gemini = lambda kw, f: "AI가 쓴 문구"
        assert {x["source"] for x in c.post(CANDIDATES, headers=ADMIN).json()} == {"ai"}

        def boom(kw, f):
            raise httpx.ConnectError("실패")
        c.app.state.sms_candidates._ask_gemini = boom  # AI 호출이 실패하면 템플릿으로 대신한다
        assert {x["source"] for x in c.post(CANDIDATES, headers=ADMIN).json()} == {"template"}


def test_external_context_is_saved_once_per_day():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        calls = fake_external(c, event="마포구 '홍대 거리공연' 행사 진행 중")
        first = c.get(EXTERNAL, headers=ADMIN).json()
        assert first["weather_text"] == "맑은 18도 날씨" and "홍대 거리공연" in first["event_text"]
        second = c.get(EXTERNAL, headers=ADMIN).json()
        assert second == first and calls["n"] == 1  # 두 번째는 DB에서 읽는다


def test_external_context_failure_returns_empty_and_is_retried():
    with TestClient(create_app(settings(), sms_clock=at(14))) as c:
        calls = fake_external(c, weather="", event="")
        assert c.get(EXTERNAL, headers=ADMIN).json()["weather_text"] == ""
        c.get(EXTERNAL, headers=ADMIN)
        assert calls["n"] == 2  # 빈 결과는 저장하지 않아 다시 시도한다


def test_fetch_events_filters_by_gu_and_date(monkeypatch):
    rows = [{"TITLE": "마포 공연", "GUNAME": "마포구", "STRTDATE": "2026-10-01 00:00:00.0", "END_DATE": "2026-10-30 00:00:00.0"},
            {"TITLE": "종로 공연", "GUNAME": "종로구", "STRTDATE": "2026-10-01 00:00:00.0", "END_DATE": "2026-10-30 00:00:00.0"},
            {"TITLE": "끝난 공연", "GUNAME": "마포구", "STRTDATE": "2026-09-01 00:00:00.0", "END_DATE": "2026-09-30 00:00:00.0"}]
    seen = {}

    def fake_get(url, **kw):
        seen["url"] = url
        return httpx.Response(200, json={"culturalEventInfo": {"row": rows}}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "get", fake_get)
    with TestClient(create_app(settings(seoul_openapi_key="KEY"))) as c:
        text = c.app.state.external.fetch_events("2026-10-17")
        assert text == "마포구 '마포 공연' 행사 진행 중"
        assert seen["url"] == EVENT_URL.format(key="KEY", day="2026-10-17")
        c.app.state.external.s.seoul_openapi_key = ""
        assert c.app.state.external.fetch_events("2026-10-17") == ""  # 키가 없으면 호출 없이 빈 값


def test_candidate_routes_require_admin():
    with TestClient(create_app(settings())) as c:
        assert c.post(CANDIDATES).status_code in (401, 403)
        assert c.get(EXTERNAL).status_code in (401, 403)
