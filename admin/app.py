"""관리자(OWNER) 페이지: streamlit run admin/app.py --server.port 8502

진입점: 로그인·사이드바 메뉴·화면 선택만 한다. 화면은 admin/views/, 공통 UI 조각은 admin/ui/ 에 있다.
데이터는 모두 admin_repository.py 를 거친다. DATA_SOURCE=dummy|api|auto 로 더미/서버를 바꾼다
(자세한 설명은 admin_repository.py 맨 위). 이 파일에는 데이터 출처에 대한 코드가 없다.
(폴더 이름이 pages 가 아니라 views 인 이유: Streamlit 은 pages/ 폴더를 자동 멀티페이지로 인식한다.)
"""

import importlib
import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))  # 저장소 루트: admin.*, shared.* 를 import 하기 위해

import admin_repository as repo_mod  # noqa: E402
import dashboard_stats  # noqa: E402
import order_filters  # noqa: E402

# 배포 서버가 재시작 없이 새 코드를 받으면 예전 모듈이 메모리에 남아 ImportError 가 난다.
# 상태가 없는 계산 모듈만 매 실행마다 다시 읽는다 (저장소·더미 데이터 모듈은 세션이 들고 있어서 제외).
importlib.reload(dashboard_stats)
importlib.reload(order_filters)

from admin.views.customers import page_customers  # noqa: E402
from admin.views.calls import page_calls  # noqa: E402
from admin.views.events import page_events  # noqa: E402
from admin.views.dashboard import page_dashboard  # noqa: E402
from admin.views.login import login  # noqa: E402
from admin.views.marketing import page_marketing  # noqa: E402
from admin.views.menu import page_menu  # noqa: E402
from admin.views.orders import page_orders  # noqa: E402
from admin.views.weights import page_weights  # noqa: E402
from admin_repository import DEFAULT_RULE  # noqa: E402

st.set_page_config(page_title="식당도우미 관리자", page_icon="🍺", layout="wide", initial_sidebar_state="auto")
st.html(Path(__file__).with_name("admin.css"))

PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "이벤트", "고객 등급", "주문 이력", "직원 호출", "마케팅"]

ss = st.session_state
ss.setdefault("owner", False)
ss.setdefault("repo", None)
ss.setdefault("notice", None)
ss.setdefault("token", "")
ss.setdefault("menu_editor_v", 0)  # 저장 후 표 편집 상태를 초기화하기 위한 번호
ss.setdefault("menu_cat", st.query_params.get("cat"))  # URL(?cat=)에서 복원 - 메뉴 관리에서 선택한 카테고리 id
ss.setdefault("grade_rule", dict(DEFAULT_RULE))


if not ss["owner"] and repo_mod.skip_token_login() and not ss.get("auto_login_failed"):
    # 임시: 토큰 입력 없이 입장. 실패하면 아래에서 기존 토큰 입력 화면을 보여준다. (ADMIN_SKIP_TOKEN=0 으로 끔)
    _auto = repo_mod.connect(repo_mod.default_admin_token())
    if _auto.error:
        ss["auto_login_failed"] = True
    else:
        ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, _auto.repo, repo_mod.default_admin_token(), _auto.notice

if not ss["owner"]:
    login()
    st.stop()

repo = ss["repo"]
store = repo.backend.store()
with st.sidebar:
    st.html(f'<div class="sb-brand"><div class="sb-logo">🍺</div><div><div class="sb-name">식당도우미</div>'
            f'<div class="sb-sub">관리자 콘솔</div></div></div><div class="sb-label">MENU</div>')
    # 새로고침해도 보던 메뉴가 유지되도록 URL(?page=...)에 저장하고 거기서 복원한다.
    if "nav_page" not in ss:
        ss["nav_page"] = st.query_params["page"] if st.query_params.get("page") in PAGES else PAGES[0]
    page = st.radio("메뉴", PAGES, key="nav_page", label_visibility="collapsed")
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    st.html('<div style="height:18px"></div><div class="sb-label">STORE</div>')
    st.caption(f"{store['name']} {store['branch']} · OWNER")
    st.caption("🟢 서버 데이터" if repo.source == "api" else "🧪 더미 데이터")
    st.html('<div style="height:10px"></div>')
    if st.button("로그아웃"):
        ss["owner"], ss["repo"] = False, None
        st.rerun()
if ss["notice"]:
    st.warning(ss["notice"])

{"대시보드": page_dashboard, "메뉴 관리": page_menu, "추천 가중치": page_weights, "이벤트": page_events, "고객 등급": page_customers,
 "주문 이력": page_orders, "직원 호출": page_calls, "마케팅": page_marketing}[page](repo)

# 메뉴 관리에서 고른 카테고리도 URL에 남겨 새로고침 후 복원한다 (페이지 실행 후의 최종 선택값 기준).
if page == "메뉴 관리" and ss["menu_cat"]:
    if st.query_params.get("cat") != ss["menu_cat"]:
        st.query_params["cat"] = ss["menu_cat"]
else:
    st.query_params.pop("cat", None)
if page != "마케팅":
    st.query_params.pop("tab", None)
