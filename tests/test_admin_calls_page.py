"""관리자 '직원 호출' 화면: 손님이 보낸 호출 확인·처리와 호출 항목 설정."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "backend"), str(ROOT / "admin"), str(ROOT / "user")]

import pytest
from streamlit.testing.v1 import AppTest

import admin_repository as ar
from admin.views.calls import chips, wait_text
from admin_dummy_data import DummyBackend
from test_admin_menu_page import APP, server  # noqa: F401 - server 픽스처 재사용


@pytest.fixture(params=["dummy", "api"])
def repo(request, server):  # noqa: F811
    if request.param == "api":
        for table, items in [(4, ["💧 물"]), (9, ["💳 계산 요청", "🧊 얼음"])]:  # 손님 화면이 보내는 것과 같은 요청
            assert server.post("/api/calls", json={"table_no": table, "items": items}).status_code == 201
        return ar.AdminRepository(ar.ApiBackend("admin-secret"))
    return ar.AdminRepository(DummyBackend())


def test_staff_calls_table_and_finish(repo):
    calls = repo.staff_calls()
    assert list(calls.columns) == ["call_id", "호출 시각", "테이블", "요청 항목", "처리 완료"]
    assert calls["호출 시각"].is_monotonic_decreasing and (~calls["처리 완료"]).sum() >= 2
    target = calls[~calls["처리 완료"]].iloc[0]
    repo.finish_call(target["call_id"])
    after = repo.staff_calls().set_index("call_id")
    assert after.at[target["call_id"], "처리 완료"] and len(after) == len(calls)


def test_staff_call_items_roundtrip_and_cleanup(repo):
    before = repo.staff_call_items()
    assert len(before) >= 3
    repo.save_staff_call_items([" 💧 물 ", "", "🧊 얼음", None])
    assert repo.staff_call_items() == ["💧 물", "🧊 얼음"]


@pytest.mark.parametrize("items, msg", [
    ([" ", ""], "하나 이상"),
    ([f"항목{i}" for i in range(13)], "12개"),
    (["가" * 21], "20자"),
    (["물", "물"], "같은 이름"),
])
def test_save_staff_call_items_rejects_bad_input(repo, items, msg):
    with pytest.raises(ar.CategoryError, match=msg):
        repo.save_staff_call_items(items)


def test_wait_text_and_chips():
    now = datetime(2026, 10, 14, 20, 0)
    assert wait_text(now, now) == "방금" and wait_text(now - timedelta(minutes=7), now) == "7분 전"
    assert wait_text(now - timedelta(minutes=135), now) == "2시간 15분 전"
    assert wait_text(now + timedelta(minutes=3), now) == "방금"  # 시계가 어긋나도 음수가 나오지 않는다
    assert chips("💧 물, <b>x</b>").count("call-chip") == 2 and "<b>" not in chips("<b>x</b>")


def open_calls(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    assert "직원 호출" in app.sidebar.radio[0].options
    app.sidebar.radio[0].set_value("직원 호출").run()
    assert not app.exception
    return app


def waiting_buttons(app):
    return [b for b in app.button if b.key and b.key.startswith("call_done_")]


def test_page_lists_waiting_calls_and_finishes_one(monkeypatch):
    app = open_calls(monkeypatch)
    assert any("대기 중 호출" in h.value for h in app.get("html"))
    before = waiting_buttons(app)
    assert len(before) == 3 and any("7" in h.value and "번 테이블" in h.value for h in app.get("html"))
    before[0].click().run()
    assert not app.exception and len(waiting_buttons(app)) == 2


def test_page_tabs_history_and_items(monkeypatch):
    app = open_calls(monkeypatch)
    app.radio(key="call_tab").set_value("처리 내역").run()
    assert not app.exception and len(app.dataframe[0].value) == 3
    app.radio(key="call_tab").set_value("호출 항목 설정").run()
    assert not app.exception
    assert app.button(key="call_items_save").disabled and app.button(key="call_items_undo").disabled  # 바뀐 게 없으면 비활성
