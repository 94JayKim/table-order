"""마케팅 화면의 대시보드/AI 탭 (더미 데이터, 키 없이 동작하는 규칙 기반 응답)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]

import pytest
from streamlit.testing.v1 import AppTest

import admin_repository as repo_mod
import marketing_ai

APP = str(ROOT / "admin" / "app.py")


@pytest.fixture(autouse=True)
def dummy_mode(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")


def open_marketing(tab=None):
    app = AppTest.from_file(APP, default_timeout=30)
    app.query_params["page"] = "마케팅"
    if tab:
        app.query_params["tab"] = tab
    app.run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_ai_context_and_recommendations():
    repo = repo_mod.connect("change-me").repo
    ctx = marketing_ai.build_context(repo, repo_mod.DEFAULT_RULE)
    assert ctx["members"]["total"] > 0 and ctx["orders"]["count"] > 0
    recs = marketing_ai.recommend(ctx)
    assert recs and all({"title", "why", "action"} <= r.keys() for r in recs)
    answer = marketing_ai.get_client().reply("인기 메뉴가 뭐야?", ctx)
    assert "가장 많이 팔린 메뉴" in answer


def test_default_tab_is_dashboard():
    app = open_marketing()
    assert not app.exception
    assert app.query_params["tab"] == "대시보드"
    assert app.text_area  # 문자 작성 화면


def test_ai_tab_from_url_shows_recommendations_and_chat():
    app = open_marketing("AI")
    assert not app.exception
    assert not app.text_area  # 대시보드 탭의 문자 작성 화면은 보이지 않는다
    app.chat_input[0].set_value("휴면 고객 어떻게 되찾을까?").run()
    assert not app.exception
    texts = [m.markdown[0].value if m.markdown else "" for m in app.chat_message]
    assert len(texts) == 3 and "휴면" in texts[-1]


def test_switching_tab_updates_url():
    app = open_marketing()
    app.radio(key="mk_tab").set_value("AI").run()
    assert app.query_params["tab"] == "AI"


def test_keyword_recipients_and_combos():
    assert marketing_ai.keyword_grades(["휴면"]) == ["휴면"]
    assert marketing_ai.keyword_grades(["주문", "단골"]) == ["단골"]
    assert marketing_ai.keyword_grades(["휴면", "단골"]) == []  # 교집합이 비면 빈 목록
    combos = marketing_ai.keyword_combos()
    assert ("휴면", "단골") not in combos and ("주문", "단골") in combos
    assert all(marketing_ai.keyword_grades(c) for c in combos)


def test_generate_sms_falls_back_to_template(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    repo = repo_mod.connect("change-me").repo
    ctx = marketing_ai.build_context(repo, repo_mod.DEFAULT_RULE)
    text, source = marketing_ai.generate_sms(["날씨", "행사"], ctx, weather="비 오는 날", event="치맥 데이")
    assert source == "template" and "비 오는 날" in text and "치맥 데이" in text


def test_generate_sms_uses_ai_and_survives_failure(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    ctx = marketing_ai.build_context(repo_mod.connect("change-me").repo, repo_mod.DEFAULT_RULE)
    monkeypatch.setattr(marketing_ai, "_ask_claude", lambda *a: "AI 문구")
    assert marketing_ai.generate_sms(["주문"], ctx) == ("AI 문구", "ai")

    def boom(*a):
        raise marketing_ai.httpx.ConnectError("x")
    monkeypatch.setattr(marketing_ai, "_ask_claude", boom)
    assert marketing_ai.generate_sms(["주문"], ctx)[1] == "template"


def test_ai_sms_button_fills_recipients_and_body(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    app = open_marketing()
    app.button(key="ai_sms_toggle").click().run()
    app.button(key="aikw_휴면").click().run()
    assert not app.exception
    assert app.multiselect(key="sms_grades").value == ["휴면"]
    assert "10% 할인" in app.text_area(key="sms_body").value
    app.button(key="aikw_주문_단골").click().run()
    assert app.multiselect(key="sms_grades").value == ["단골"]
