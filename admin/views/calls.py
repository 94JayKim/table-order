"""직원 호출 화면: 손님이 테이블에서 보낸 호출을 확인하고 처리하며, 손님 화면의 호출 항목을 설정한다.

탭: 대기 중(처리 버튼, 자동 새로고침) / 처리 내역 / 호출 항목 설정
"""

from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from admin.ui.widgets import kpi, kpi_row, page_head, sec_title
from admin_repository import KST, STAFF_CALL_MAX_ITEMS, STAFF_CALL_MAX_LEN, CategoryError

ss = st.session_state
CALL_TABS = ["대기 중", "처리 내역", "호출 항목 설정"]
REFRESH_SECONDS = 15


def now_kst() -> datetime:
    return datetime.now(KST).replace(tzinfo=None)


def wait_text(called_at: datetime, now: datetime) -> str:
    """'방금 / N분 전 / N시간 N분 전' 형태의 경과 시간."""
    minutes = max(int((now - called_at).total_seconds() // 60), 0)
    if minutes < 1:
        return "방금"
    return f"{minutes}분 전" if minutes < 60 else f"{minutes // 60}시간 {minutes % 60}분 전"


def chips(items: str) -> str:
    return "".join(f'<span class="call-chip">{escape(i.strip())}</span>' for i in items.split(",") if i.strip())


def finish(repo, call_id):
    try:
        repo.finish_call(call_id)
    except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
        ss["call_error"] = f"처리하지 못했습니다: {e}"
    else:
        ss["call_notice"] = "호출을 처리 완료로 바꿨어요."


@st.fragment(run_every=REFRESH_SECONDS)
def render_waiting(repo):
    calls = repo.staff_calls()
    now = now_kst()
    waiting = calls[~calls["처리 완료"]].sort_values("호출 시각", ignore_index=True)  # 오래 기다린 호출이 위
    done_today = calls[calls["처리 완료"] & (calls["호출 시각"].dt.date == now.date())]
    oldest = wait_text(waiting.iloc[0]["호출 시각"], now) if len(waiting) else "-"
    kpi_row(kpi("대기 중 호출", len(waiting), "건", accent=bool(len(waiting))),
            kpi("오늘 처리한 호출", len(done_today), "건"),
            kpi("가장 오래 기다린 호출", oldest, sub="처리하지 않은 호출 중"))
    st.html('<div style="height:16px"></div>')
    if error := ss.pop("call_error", None):
        st.error(error)
    if ss.get("call_notice"):
        st.toast(ss.pop("call_notice"), icon="✅")
    sec_title("대기 중인 호출", f"{REFRESH_SECONDS}초마다 자동으로 새로고침돼요")
    if waiting.empty:
        st.html('<div class="empty">대기 중인 호출이 없어요. 🎉</div>')
        return
    for _, c in waiting.iterrows():
        with st.container(border=True, key=f"call_{c['call_id']}"):
            t, body, w, btn = st.columns([1.5, 4.6, 1.6, 1.6], vertical_alignment="center")
            t.html(f'<div class="call-table">{int(c["테이블"])}<small>번 테이블</small></div>')
            body.html(f'<div class="call-items">{chips(c["요청 항목"])}</div>')
            w.html(f'<div class="call-wait">{escape(wait_text(c["호출 시각"], now))}<small>{c["호출 시각"]:%H:%M} 호출</small></div>')
            btn.button("처리 완료", key=f"call_done_{c['call_id']}", type="primary", width="stretch",
                       on_click=finish, args=(repo, int(c["call_id"])))


def render_history(repo):
    calls = repo.staff_calls()
    done = calls[calls["처리 완료"]]
    sec_title("처리 내역", f"{len(done)}건")
    if done.empty:
        st.html('<div class="empty">아직 처리한 호출이 없어요.</div>')
        return
    shown = done.drop(columns=["call_id", "처리 완료"]).assign(상태="처리 완료")
    st.dataframe(shown, hide_index=True, width="stretch",
                 column_config={"호출 시각": st.column_config.DatetimeColumn(format="MM-DD HH:mm"),
                                "테이블": st.column_config.NumberColumn(format="%d번")})


def render_items(repo):
    old = pd.DataFrame({"호출 항목": repo.staff_call_items()})
    sec_title("호출 항목 설정", "손님 주문 화면의 직원 호출 창에 이 순서대로 보여요")
    edited = st.data_editor(
        old, hide_index=True, width="stretch", num_rows="dynamic", height=min(480, 90 + 36 * (len(old) + 1)),
        key=f"call_items_editor_{ss['call_items_v']}",
        column_config={"호출 항목": st.column_config.TextColumn(required=True, max_chars=STAFF_CALL_MAX_LEN,
                                                             help="앞에 이모지를 붙이면 손님 화면에서 구분하기 쉬워요 (예: 💧 물)")})
    st.caption(f"항목은 {STAFF_CALL_MAX_ITEMS}개까지, 이름은 {STAFF_CALL_MAX_LEN}자 이하. 표 아래 빈 줄에서 추가하고 행을 선택해 지울 수 있어요.")
    new = edited.reset_index(drop=True)
    dirty = list(new["호출 항목"].fillna("")) != list(old["호출 항목"])
    c_save, c_undo, _ = st.columns([1, 1.3, 5])
    if c_undo.button("↩ 되돌리기", key="call_items_undo", width="stretch", disabled=not dirty,
                     help="저장하기 전의 변경을 모두 취소하고 저장된 값으로 돌립니다"):
        ss["call_items_v"] += 1
        st.toast("저장하지 않은 변경을 되돌렸어요.", icon="↩️")
        st.rerun()
    if c_save.button("변경 저장", type="primary", key="call_items_save", width="stretch", disabled=not dirty):
        try:
            repo.save_staff_call_items(list(new["호출 항목"]))
        except CategoryError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["call_items_v"] += 1
            st.toast("호출 항목을 저장했습니다. 손님 화면에는 잠시 뒤 반영돼요.", icon="✅")
            st.rerun()


def page_calls(repo):
    page_head("직원 호출", "손님이 테이블에서 보낸 호출을 확인하고 처리해요")
    ss.setdefault("call_items_v", 0)
    tab = st.radio("직원 호출 탭", CALL_TABS, key="call_tab", horizontal=True, label_visibility="collapsed")
    {"대기 중": render_waiting, "처리 내역": render_history, "호출 항목 설정": render_items}[tab](repo)
