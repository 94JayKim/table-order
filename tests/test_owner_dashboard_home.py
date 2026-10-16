"""관리자 로그인 직후 대시보드 첫 화면과 사이드바 순서 테스트."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "admin")]
APP = str(ROOT / "admin" / "app.py")


def open_dashboard(monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "dummy")
    monkeypatch.setenv("APP_ENV", "prod")
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.text_input[0].set_value("change-me")
    app.button[0].click().run()
    return app


def test_dashboard_is_first_and_combines_today_with_sales_trend(monkeypatch):
    app = open_dashboard(monkeypatch)

    assert not app.exception
    assert app.query_params["page"] == "대시보드"
    assert app.query_params["tab"] == "한눈에 보기"
    assert app.sidebar.expander[0].label == "📊 대시보드"
    assert app.sidebar.radio(key="nav_sub_대시보드").options[0] == "한눈에 보기"

    html = "\n".join(element.value for element in app.get("html"))
    assert "오늘 주문" in html and "최근 7일 매출" in html and "일별 매출 (최근 14일)" in html
    assert html.index("일별 매출 (최근 14일)") < html.index("인기 메뉴 TOP 10")
