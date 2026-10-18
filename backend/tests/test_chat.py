"""AI 챗봇(/admin/api/marketing/chat/sessions…) 테스트. 제미나이 호출은 가짜로 바꿔 끼운다."""

import httpx
from fastapi.testclient import TestClient

from app.factory import create_app
from app.services import chat as chat_service
from tests.conftest import ADMIN, settings

BASE = "/admin/api/marketing/chat/sessions"
OWNER = "11111111-1111-1111-1111-111111111111"


def make(**kw):
    return TestClient(create_app(settings(chat_owner_id=OWNER, **kw)))


def fake_gemini(monkeypatch, reply="지난주 매출은 0원이에요.", fail=None):
    """제미나이 대신 정해 둔 답을 돌려주고, 받은 시스템 프롬프트·대화를 기록한다."""
    seen = {}

    def ask(self, system, history, question):
        seen.update(system=system, history=history, question=question)
        if fail:
            raise fail
        return reply
    monkeypatch.setattr(chat_service.ChatService, "_ask_gemini", ask)
    return seen


def test_create_session_has_greeting_and_lists_recent_first():
    with make() as c:
        a = c.post(BASE, headers=ADMIN)
        assert a.status_code == 201
        assert [m["role"] for m in a.json()["messages"]] == ["assistant"]
        b = c.post(BASE, headers=ADMIN).json()
        ids = [s["id"] for s in c.get(BASE, headers=ADMIN).json()]
        assert ids == [b["id"], a.json()["id"]]  # 최근에 만든 대화가 먼저


def test_question_saves_user_and_assistant_messages(monkeypatch):
    seen = fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "저번주 총 매출 알려줘"})
        assert r.status_code == 201
        assert [m["role"] for m in r.json()["messages"]] == ["user", "assistant"]
        session = c.get(f"{BASE}/{sid}", headers=ADMIN).json()
        assert [m["role"] for m in session["messages"]] == ["assistant", "user", "assistant"]
        assert session["title"] == "저번주 총 매출 알려줘"  # 첫 질문이 제목
    assert "저번 주" in seen["system"] and "[매장 데이터]" in seen["system"]
    assert seen["question"] == "저번주 총 매출 알려줘"


def test_summary_sums_last_week_by_server(monkeypatch):
    """제미나이가 아니라 서버가 지난주 합계를 계산해 프롬프트에 넣는다."""
    seen = fake_gemini(monkeypatch)
    # 오늘 기준 지난주 월요일 낮(KST)에 3만원 + 2만원 주문을 직접 넣는다
    from datetime import datetime, timedelta
    from app.services.grades import KST
    today = datetime.now(KST).date()
    monday = today - timedelta(days=today.weekday() + 7)
    stamp = datetime(monday.year, monday.month, monday.day, 12, tzinfo=KST).isoformat()
    with make(gemini_api_key="k") as c:
        db = c.app.state.db
        for total in (30000, 20000):
            db.run("INSERT INTO orders (table_no, total, created_at) VALUES (?,?,?)", (1, total, stamp))
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "저번주 매출?"})
    assert "매출 50,000원, 주문 2건" in seen["system"]


def test_history_is_sent_without_leading_greeting(monkeypatch):
    seen = fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "첫 질문"})
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "둘째 질문"})
    assert [m["content"] for m in seen["history"] if m["role"] == "user"] == ["첫 질문"]


def test_no_api_key_answers_with_guide_not_500():
    with make(gemini_api_key="") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 201
        assert "GEMINI_API_KEY" in r.json()["messages"][1]["content"]


def test_gemini_failure_returns_error_and_saves_nothing(monkeypatch):
    fake_gemini(monkeypatch, fail=httpx.ConnectError("down"))
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 502
        assert len(c.get(f"{BASE}/{sid}", headers=ADMIN).json()["messages"]) == 1  # 인사 메시지뿐


def test_rate_limit_message(monkeypatch):
    resp = httpx.Response(429, request=httpx.Request("POST", "http://x"))
    fake_gemini(monkeypatch, fail=httpx.HTTPStatusError("limit", request=resp.request, response=resp))
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        r = c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "오늘 매출"})
        assert r.status_code == 502 and "한도" in r.json()["detail"]


def test_delete_removes_messages_and_missing_is_404(monkeypatch):
    fake_gemini(monkeypatch)
    with make(gemini_api_key="k") as c:
        sid = c.post(BASE, headers=ADMIN).json()["id"]
        c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "질문"})
        assert c.delete(f"{BASE}/{sid}", headers=ADMIN).status_code == 204
        assert c.get(f"{BASE}/{sid}", headers=ADMIN).status_code == 404
        assert c.app.state.db.one("SELECT COUNT(*) AS n FROM chat_messages")["n"] == 0
        assert c.delete(f"{BASE}/{sid}", headers=ADMIN).status_code == 404
        assert c.get(f"{BASE}/not-a-uuid", headers=ADMIN).status_code == 404
        assert c.post(f"{BASE}/{sid}/messages", headers=ADMIN, json={"content": "x"}).status_code == 404


def test_missing_owner_setting_is_not_500():
    with TestClient(create_app(settings(chat_owner_id=""))) as c:
        r = c.post(BASE, headers=ADMIN)
        assert r.status_code == 503 and "CHAT_OWNER_ID" in r.json()["detail"]


def test_requires_admin_token():
    with make() as c:
        assert c.post(BASE).status_code == 401
