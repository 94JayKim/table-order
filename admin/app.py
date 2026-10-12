"""관리자(OWNER) 페이지: streamlit run admin/app.py --server.port 8502

데이터는 모두 admin_repository.py 를 거친다. DATA_SOURCE=dummy|api|auto 로 더미/서버를 바꾼다
(자세한 설명은 admin_repository.py 맨 위). 이 파일에는 데이터 출처에 대한 코드가 없다.
"""

import pandas as pd
import streamlit as st

import admin_repository as repo_mod
from admin_dummy_data import Unsupported
from admin_repository import DEFAULT_RULE, GRADES, SPICY_LABELS

st.set_page_config(page_title="식당도우미 관리자", page_icon="🛠️", layout="wide")

PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]

ss = st.session_state
ss.setdefault("owner", False)
ss.setdefault("repo", None)
ss.setdefault("notice", None)
ss.setdefault("token", "")
ss.setdefault("menu_editor_v", 0)  # 저장 후 표 편집 상태를 초기화하기 위한 번호
ss.setdefault("grade_rule", dict(DEFAULT_RULE))


def login():
    st.title("🛠️ 식당도우미 관리자")
    st.caption("OWNER(사장님)만 접근할 수 있습니다. MANAGER·STAFF 권한은 1차 Prototype에서 사용하지 않습니다.")
    token = st.text_input("관리자 토큰", type="password")
    if st.button("로그인", type="primary"):
        result = repo_mod.connect(token)
        if result.error:
            st.error(result.error)
        else:
            ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, result.repo, token, result.notice
            st.rerun()
    st.info("백엔드 `.env`의 `ADMIN_TOKEN` 값을 입력하세요. (기본값 `change-me`)")


def page_dashboard(repo):
    s = repo.stats(ss["grade_rule"])
    st.subheader("주문 통계")
    a, b, c, d = st.columns(4)
    a.metric("오늘 주문 수", f"{s['today_orders']}건")
    b.metric("평균 주문금액", f"{s['avg_order_amount']:,}원" if s["today_orders"] else "-")
    c.metric("오늘 신규 고객", f"{s['new_customers']}명")
    d.metric("오늘 재방문 고객", f"{s['returning_customers']}명")

    st.subheader("고객 분석")
    l, r = st.columns(2)
    with l:
        st.caption("고객 연령대 (출생연도를 입력한 회원만)")
        st.bar_chart(pd.Series(s["age_groups"], dtype="float"))
    with r:
        st.caption("고객 성별")
        if s["genders"]:
            st.bar_chart(pd.Series(s["genders"], dtype="float"))
        else:
            st.write("아직 데이터가 없어요.")

    l, r = st.columns(2)
    with l:
        st.subheader("인기 메뉴 TOP 10")
        if s["popular_menus"]:
            st.bar_chart(pd.Series({m["name"]: m["qty"] for m in s["popular_menus"]}, dtype="float"), horizontal=True)
        else:
            st.write("아직 주문이 없어요.")
    with r:
        st.subheader("AI 추천 분석")
        ai = s["ai"]
        st.metric("AI 추천 적중률", f"{ai['hit_rate']:.0%}" if ai["hit_rate"] is not None else "-")
        st.caption(f"임시 기준: {ai['definition']}. 정확한 계산 기준은 추가 정의가 필요합니다.")
        st.metric("AI 추천 노출 / 조합이 포함된 주문", f"{ai['recommendations']}회 / {ai['ai_orders']}건")


def menu_editor(repo, key_prefix: str, **kw):
    df = repo.menus()
    return df, st.data_editor(
        df, hide_index=True, width="stretch", num_rows="dynamic", disabled=["id"], height=520,
        key=f"{key_prefix}_{ss['menu_editor_v']}", **kw)


def page_menu(repo):
    st.subheader("메뉴 관리")
    st.caption("메뉴명·가격·설명·이미지·판매 여부·매운 정도·카테고리·추천 가중치·세트 가능 여부를 수정합니다. 행 추가·삭제도 가능해요.")
    names = [c["name"] for c in repo.categories()]
    old, edited = menu_editor(repo, "menu_editor", column_config={
        "카테고리": st.column_config.SelectboxColumn(options=names, required=True),
        "메뉴명": st.column_config.TextColumn(required=True),
        "가격": st.column_config.NumberColumn(min_value=0, step=500, format="%d원", required=True),
        "매운 정도": st.column_config.SelectboxColumn(options=list(SPICY_LABELS.values()), required=True),
        "추천 가중치": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, required=True),
        "이미지 URL": st.column_config.LinkColumn(),
        "판매 여부": st.column_config.CheckboxColumn(),
        "세트 가능": st.column_config.CheckboxColumn(),
    })
    if st.button("저장", type="primary"):
        try:
            r = repo.save_menus(edited.reset_index(drop=True), old)
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["menu_editor_v"] += 1
            st.toast(f"저장했습니다. (수정 {r['saved']}개, 삭제 {r['deleted']}개)", icon="✅")
            st.rerun()


def page_weights(repo):
    st.subheader("OWNER 추천 가중치")
    st.caption("0~100. 높을수록 AI 추천 조합에 우선 반영됩니다. 50이 기본값입니다.")
    menu = repo.menus()
    cat = st.selectbox("카테고리", ["전체"] + [c["name"] for c in repo.categories()])
    view = menu if cat == "전체" else menu[menu["카테고리"] == cat]
    new = menu.copy()
    for idx, row in view.iterrows():
        c1, c2 = st.columns([2, 3])
        c1.write(f"**{row['메뉴명']}**" + ("" if row["판매 여부"] else " (품절)"))
        new.at[idx, "추천 가중치"] = c2.slider(row["메뉴명"], 0, 100, int(row["추천 가중치"]), 5,
                                           key=f"w_{row['id']}", label_visibility="collapsed")
    if st.button("가중치 저장", type="primary"):
        r = repo.save_menus(new, menu)
        st.toast(f"저장했습니다. (수정 {r['saved']}개)", icon="✅")


def page_customers(repo):
    st.subheader("고객 등급 관리")
    rule = ss["grade_rule"]
    with st.expander("등급 분류 기준 (임시 — 추가 정의 필요)", expanded=True):
        c1, c2, c3 = st.columns(3)
        rule["repeat"] = c1.number_input("재방문: 방문 횟수 ≥", 2, 50, rule["repeat"])
        rule["regular"] = c2.number_input("단골: 방문 횟수 ≥", rule["repeat"] + 1, 100, max(rule["regular"], rule["repeat"] + 1))
        rule["dormant"] = c3.number_input("휴면: 마지막 방문 후 N일 이상", 7, 365, rule["dormant"])
        st.caption("그 외(방문 1회)는 신규 고객입니다. 이 값은 화면에서 미리 보는 용도이고 서버에는 저장되지 않아요.")
    cust = repo.members(rule)
    cols = st.columns(4)
    for col, g in zip(cols, GRADES):
        col.metric(f"{g} 고객", f"{(cust['등급'] == g).sum()}명")
    pick = st.multiselect("등급 필터", GRADES, default=GRADES)
    st.dataframe(cust[cust["등급"].isin(pick)], hide_index=True, width="stretch")


def page_orders(repo):
    st.subheader("주문 이력")
    orders = repo.orders()
    cust = repo.members(ss["grade_rule"]).set_index("customer_id")
    mode = st.radio("보기", ["전체 주문", "고객별 주문"], horizontal=True)
    if mode == "고객별 주문":
        if cust.empty:
            st.info("아직 회원이 없어요.")
            return
        who = st.selectbox("고객", cust.index, format_func=lambda i: f"{cust.at[i, '닉네임']} ({i}) · {cust.at[i, '등급']}")
        orders = orders[orders["customer_id"] == who]
        st.metric("누적 주문 금액", f"{int(orders['금액'].sum()):,}원")
    st.dataframe(orders, hide_index=True, width="stretch",
                 column_config={"금액": st.column_config.NumberColumn(format="%d원")})


def page_marketing(repo):
    st.subheader("마케팅 지원 · 문자 발송")
    try:
        usage = repo.sms_usage()
    except Unsupported as e:
        st.info(f"{e} 서버를 켜고 `DATA_SOURCE=api` (또는 auto)로 실행하세요.")
        return
    except (repo_mod.api.ApiError, repo_mod.api.ApiUnavailable) as e:
        st.error(f"서버에서 정보를 가져오지 못했습니다: {e}")
        return
    st.caption("수신 동의·휴대폰 번호가 있는 회원에게만, 야간(21~08시) 제외, 월 무료 한도 안에서 발송합니다. "
               "서버 설정 `SMS_DRY_RUN=true` 이면 실제 문자는 전송되지 않고 기록만 남습니다.")
    c1, c2 = st.columns(2)
    c1.metric("이번 달 SMS", f"{usage['used']['SMS']} / {usage['limit']['SMS']}건")
    c2.metric("이번 달 LMS", f"{usage['used']['LMS']} / {usage['limit']['LMS']}건")

    grades = st.multiselect("대상 등급", GRADES, default=["휴면"])
    body = st.text_area("본문", "오랜만이에요! 이번 주 방문하시면 안주 10% 할인해 드려요.")
    plan = None
    if grades:
        try:
            plan = repo.sms_preview(grades, body)
        except repo_mod.api.ApiError as e:
            st.error(f"미리보기에 실패했습니다: {e.detail}")
    if plan:
        st.text_area("실제 발송 문구 (광고 표기·수신거부 안내 자동 추가)", plan["content"], disabled=True, height=110)
        st.caption(f"{plan['bytes']}바이트 → **{plan['type']}** · 발송 대상 {plan['targets']}명 · 잔여 {plan['remaining']}건"
                   + (" · 🧪 DRY RUN (실제 전송 없음)" if plan["dry_run"] else ""))
        for problem in plan["problems"]:
            st.warning(problem)
    if st.button("발송", type="primary", disabled=not (plan and plan["ok"])):
        try:
            r = repo.sms_send(grades, body)
            st.toast(f"{r['count']}명 발송 처리했습니다." + (" (DRY RUN)" if r["dry_run"] else ""), icon="✅")
        except repo_mod.api.ApiError as e:
            problems = e.detail.get("problems", []) if isinstance(e.detail, dict) else [str(e.detail)]
            st.error("발송하지 못했습니다: " + " / ".join(problems))
        else:
            st.rerun()

    with st.expander("수신거부 처리"):
        members = repo.members(ss["grade_rule"])
        pool = members[members["마케팅 수신 동의"] & ~members["수신거부"]]
        if not pool.empty:
            who = st.selectbox("회원", pool["customer_id"],
                               format_func=lambda i: f"#{i} {pool.set_index('customer_id').at[i, '닉네임']}")
            if st.button("수신거부로 등록"):
                repo.opt_out(int(who))
                st.rerun()
        else:
            st.caption("수신 동의한 회원이 없습니다.")
        st.caption(f"수신거부 회원 {int(members['수신거부'].sum())}명 — 발송 대상에서 제외됩니다. (회원 본인은 태블릿에서도 거부할 수 있어요)")

    logs = repo.sms_logs()
    if logs:
        st.write("발송 내역")
        st.dataframe(pd.DataFrame(logs)[["ts", "type", "status", "target_count", "request_id", "error", "content"]],
                     hide_index=True, width="stretch")


if not ss["owner"]:
    login()
    st.stop()

repo = ss["repo"]
store = repo.backend.store()
with st.sidebar:
    st.title("🛠️ 관리자")
    st.caption(f"{store['name']} {store['branch']} · OWNER")
    st.caption("🟢 서버 데이터" if repo.source == "api" else "🧪 더미 데이터")
    page = st.radio("메뉴", PAGES, label_visibility="collapsed")
    if st.button("로그아웃"):
        ss["owner"], ss["repo"] = False, None
        st.rerun()
if ss["notice"]:
    st.warning(ss["notice"])

{"대시보드": page_dashboard, "메뉴 관리": page_menu, "추천 가중치": page_weights, "고객 등급": page_customers,
 "주문 이력": page_orders, "마케팅": page_marketing}[page](repo)
