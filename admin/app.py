"""관리자(OWNER) 페이지: streamlit run admin/app.py --server.port 8502

데이터는 모두 admin_repository.py 를 거친다. DATA_SOURCE=dummy|api|auto 로 더미/서버를 바꾼다
(자세한 설명은 admin_repository.py 맨 위). 이 파일에는 데이터 출처에 대한 코드가 없다.
"""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import admin_repository as repo_mod
from admin_dummy_data import Unsupported
from admin_repository import COLOR_PRESETS, DEFAULT_RULE, GRADES, ICON_DEFAULT, SPICY_LABELS, CategoryError

st.set_page_config(page_title="식당도우미 관리자", page_icon="🍺", layout="wide", initial_sidebar_state="expanded")
st.html(Path(__file__).with_name("admin.css"))

PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]

ss = st.session_state
ss.setdefault("owner", False)
ss.setdefault("repo", None)
ss.setdefault("notice", None)
ss.setdefault("token", "")
ss.setdefault("menu_editor_v", 0)  # 저장 후 표 편집 상태를 초기화하기 위한 번호
ss.setdefault("menu_cat", None)  # 메뉴 관리에서 선택한 카테고리 id
ss.setdefault("grade_rule", dict(DEFAULT_RULE))


def page_head(title, sub=""):
    st.html(f'<div class="page-head"><div><h1>{escape(title)}</h1>'
            + (f"<p>{escape(sub)}</p>" if sub else "") + "</div></div>")


def sec_title(text, small=""):
    st.html(f'<div class="sec-title">{escape(text)}' + (f" <small>{escape(small)}</small>" if small else "") + "</div>")


def kpi(label, value, unit="", sub="", accent=False):
    return (f'<div class="kpi{" accent" if accent else ""}"><div class="k">{escape(label)}</div>'
            f'<div class="v">{escape(str(value))}<small>{escape(unit)}</small></div>'
            + (f'<div class="s">{escape(sub)}</div>' if sub else "") + "</div>")


def kpi_row(*cards):
    st.html('<div class="kpis">' + "".join(cards) + "</div>")


def bars(data, unit="", ranked=False, empty="아직 데이터가 없어요."):
    """가로 막대 목록(HTML). data: {이름: 값}"""
    if not data:
        return f'<div class="empty">{escape(empty)}</div>'
    top = max(data.values()) or 1
    rows = "".join(
        f'<div class="bar-row"><span class="n" data-r="{i}">{escape(str(k))}</span>'
        f'<span class="t"><i style="width:{max(v / top * 100, 2):.0f}%"></i></span><span class="c">{v:g}{unit}</span></div>'
        for i, (k, v) in enumerate(data.items(), 1))
    return f'<div class="bars{" rank-list" if ranked else ""}">{rows}</div>'


def panel(title, hint, body):
    return f'<div class="panel"><h3>{escape(title)}</h3><div class="hint">{escape(hint)}</div>{body}</div>'


def login():
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.html('<div style="height:8vh"></div><div style="text-align:center;margin-bottom:22px">'
                '<div class="sb-logo" style="width:56px;height:56px;border-radius:16px;font-size:30px;margin:0 auto 14px">🍺</div>'
                '<div style="font-size:26px;font-weight:800;letter-spacing:-.02em">식당도우미 관리자</div>'
                '<div style="color:#8a857e;font-size:14px;margin-top:6px">사장님 전용 관리 화면이에요</div></div>')
        with st.container(border=True):
            token = st.text_input("관리자 토큰", type="password", placeholder="토큰을 입력하세요")
            if st.button("로그인", type="primary", width="stretch"):
                result = repo_mod.connect(token)
                if result.error:
                    st.error(result.error)
                else:
                    ss["owner"], ss["repo"], ss["token"], ss["notice"] = True, result.repo, token, result.notice
                    st.rerun()
        st.caption("백엔드 `.env`의 `ADMIN_TOKEN` 값을 입력하세요. (기본값 `change-me`) "
                   "OWNER(사장님)만 접근할 수 있고, MANAGER·STAFF 권한은 1차 Prototype에서 사용하지 않습니다.")


def page_dashboard(repo):
    s = repo.stats(ss["grade_rule"])
    ai = s["ai"]
    page_head("대시보드", "오늘 매장 현황을 한눈에 확인하세요")
    kpi_row(
        kpi("오늘 주문", s["today_orders"], "건", accent=True),
        kpi("평균 주문금액", f"{s['avg_order_amount']:,}" if s["today_orders"] else "-", "원" if s["today_orders"] else ""),
        kpi("오늘 신규 고객", s["new_customers"], "명"),
        kpi("오늘 재방문 고객", s["returning_customers"], "명"),
    )
    sec_title("고객 분석")
    l, r = st.columns(2, gap="medium")
    l.html(panel("고객 연령대", "출생연도를 입력한 회원만 집계해요", bars(s["age_groups"], "명")))
    r.html(panel("고객 성별", "회원 정보 기준", bars(s["genders"], "명")))
    sec_title("메뉴 · AI 추천")
    l, r = st.columns([3, 2], gap="medium")
    l.html(panel("인기 메뉴 TOP 10", "주문 수량 기준",
                 bars({m["name"]: m["qty"] for m in s["popular_menus"]}, "개", ranked=True, empty="아직 주문이 없어요.")))
    with r:
        kpi_row(kpi("AI 추천 적중률", f"{ai['hit_rate']:.0%}" if ai["hit_rate"] is not None else "-",
                    sub="임시 기준 · 정확한 계산 기준은 추가 정의가 필요해요"),
                kpi("추천 노출", ai["recommendations"], "회", sub=f"조합이 포함된 주문 {ai['ai_orders']}건"))
        st.caption(f"적중 기준(임시): {ai['definition']}")


def select_category(category_id):
    ss["menu_cat"] = category_id


def render_category_panel(repo, cats):
    """왼쪽: 카테고리 목록(클릭해서 선택) + 추가·수정·삭제."""
    with st.container(border=True, key="mcat_panel"):
        st.html('<div class="mcat-title">📂 카테고리</div>')
        if not cats:
            st.html('<div class="mcat-hint">아직 카테고리가 없어요. 아래에서 추가해 보세요.</div>')
        for c in cats:
            st.button(f"{c['icon']}  {c['name']}  ({c['menu_count']})", key=f"mcat_{c['id']}", width="stretch",
                      type="primary" if ss["menu_cat"] == c["id"] else "secondary",
                      on_click=select_category, args=(c["id"],))

        with st.expander("＋ 카테고리 추가"):
            with st.form("cat_add_form", clear_on_submit=True):
                name = st.text_input("이름", placeholder="예: 세트 메뉴")
                icon = st.text_input("아이콘 (이모지)", value=ICON_DEFAULT, max_chars=4)
                color = st.selectbox("색상", list(COLOR_PRESETS))
                if st.form_submit_button("추가", type="primary", width="stretch"):
                    try:
                        ss["menu_cat"] = repo.add_category(name, icon, color)
                    except CategoryError as e:
                        st.error(str(e))
                    else:
                        st.toast("카테고리를 추가했어요. 이제 메뉴를 등록해 보세요.", icon="✅")
                        st.rerun()

        selected = next((c for c in cats if c["id"] == ss["menu_cat"]), None)
        if selected:
            with st.expander(f"✏️ '{selected['name']}' 수정·삭제"):
                with st.form(f"cat_edit_form_{selected['id']}"):
                    name = st.text_input("이름", value=selected["name"])
                    icon = st.text_input("아이콘 (이모지)", value=selected["icon"], max_chars=4)
                    color = st.selectbox("색상", ["(그대로)"] + list(COLOR_PRESETS))
                    if st.form_submit_button("수정 저장", width="stretch"):
                        try:
                            repo.update_category(selected["id"], name, icon, None if color == "(그대로)" else color)
                        except CategoryError as e:
                            st.error(str(e))
                        else:
                            st.toast("카테고리를 수정했어요.", icon="✅")
                            st.rerun()
                if selected["menu_count"]:
                    st.caption(f"메뉴 {selected['menu_count']}개가 있어서 삭제할 수 없어요. 메뉴를 먼저 정리해 주세요.")
                else:
                    sure = st.checkbox("정말 삭제할게요", key=f"cat_del_ok_{selected['id']}")
                    if st.button("🗑 카테고리 삭제", disabled=not sure, width="stretch", key="cat_delete"):
                        try:
                            repo.delete_category(selected["id"])
                        except CategoryError as e:
                            st.error(str(e))
                        else:
                            ss["menu_cat"] = None
                            st.toast("카테고리를 삭제했어요.", icon="🗑")
                            st.rerun()


def render_menu_register_form(repo, category):
    with st.expander(f"＋ '{category['name']}'에 메뉴 등록", expanded=True):
        with st.form(f"menu_add_form_{category['id']}", clear_on_submit=True):
            c1, c2 = st.columns([3, 1.4])
            name = c1.text_input("메뉴 이름 *", placeholder="예: 매운 닭볶음탕")
            price = c2.number_input("가격 *", min_value=0, step=500, value=10000)
            desc = st.text_input("설명", placeholder="손님 화면에 보이는 한 줄 설명")
            image = st.text_input("이미지 URL", placeholder="https://...")
            c3, c4, c5, c6 = st.columns(4)
            spicy = c3.selectbox("매운 정도", list(SPICY_LABELS.values()))
            weight = c4.slider("추천 가중치", 0, 100, 50, 5, help="높을수록 AI 추천 조합에 우선 반영돼요 (기본 50)")
            on_sale = c5.checkbox("판매 중", value=True)
            set_ok = c6.checkbox("세트 가능", value=True)
            if st.form_submit_button("메뉴 등록", type="primary"):
                try:
                    repo.add_menu(category["id"], name, price, desc, image, not on_sale, spicy, weight, set_ok)
                except CategoryError as e:
                    st.error(str(e))
                else:
                    ss["menu_editor_v"] += 1
                    st.toast(f"'{name.strip()}' 메뉴를 등록했어요.", icon="✅")
                    st.rerun()


def render_menu_panel(repo, cats):
    """오른쪽: 선택한 카테고리의 메뉴 등록 + 등록된 메뉴 편집."""
    category = next((c for c in cats if c["id"] == ss["menu_cat"]), None)
    if category is None:
        st.info("👈 왼쪽에서 카테고리를 클릭하면 그 카테고리에 메뉴를 등록하고 수정할 수 있어요.")
        if cats:
            st.html(panel("카테고리별 메뉴 수", "카테고리를 선택하면 메뉴를 관리할 수 있어요",
                          bars({f"{c['icon']} {c['name']}": c["menu_count"] for c in cats}, "개")))
        return
    st.html(f'<div class="mmenu-head"><b>{category["icon"]} {category["name"]}</b><span>메뉴 {category["menu_count"]}개</span></div>')
    render_menu_register_form(repo, category)

    sec_title("등록된 메뉴")
    df = repo.menus()
    old = df[df["카테고리"] == category["name"]].reset_index(drop=True)
    if old.empty:
        st.caption("아직 등록된 메뉴가 없어요. 위 양식으로 첫 메뉴를 등록해 보세요.")
        return
    edited = st.data_editor(
        old, hide_index=True, width="stretch", num_rows="dynamic", disabled=["id"], height=min(520, 80 + 36 * len(old)),
        key=f"menu_editor_{category['id']}_{ss['menu_editor_v']}",
        column_config={
            "id": None, "카테고리": None,
            "메뉴명": st.column_config.TextColumn(required=True),
            "가격": st.column_config.NumberColumn(min_value=0, step=500, format="%d원", required=True),
            "매운 정도": st.column_config.SelectboxColumn(options=list(SPICY_LABELS.values()), required=True),
            "추천 가중치": st.column_config.NumberColumn(min_value=0, max_value=100, step=5, required=True),
            "이미지 URL": st.column_config.LinkColumn(),
            "판매 여부": st.column_config.CheckboxColumn(),
            "세트 가능": st.column_config.CheckboxColumn(),
        })
    st.caption("표에서 직접 고치거나 행을 추가·삭제한 뒤 저장하세요.")
    if st.button("변경 저장", type="primary", key="menu_save"):
        new = edited.reset_index(drop=True)
        new["카테고리"] = category["name"]  # 표에서 새로 추가한 행도 이 카테고리에 들어간다
        try:
            r = repo.save_menus(new, old)
        except Exception as e:  # noqa: BLE001 - 서버 오류 메시지를 그대로 보여준다
            st.error(f"저장하지 못했습니다: {e}")
        else:
            ss["menu_editor_v"] += 1
            st.toast(f"저장했습니다. (수정 {r['saved']}개, 삭제 {r['deleted']}개)", icon="✅")
            st.rerun()


def page_menu(repo):
    page_head("메뉴 관리", "카테고리를 고른 뒤 메뉴를 등록하고 수정하세요")
    cats = repo.category_list()
    if ss["menu_cat"] and ss["menu_cat"] not in {c["id"] for c in cats}:
        ss["menu_cat"] = None  # 지워졌거나 서버에서 사라진 카테고리
    left, right = st.columns([1.15, 3.6], gap="large")
    with left:
        render_category_panel(repo, cats)
    with right:
        render_menu_panel(repo, cats)


def page_weights(repo):
    page_head("추천 가중치", "0~100. 높을수록 AI 추천 조합에 우선 반영됩니다. 50이 기본값입니다.")
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
    page_head("고객 등급", "방문 이력으로 고객을 신규·재방문·단골·휴면으로 나눠요")
    rule = ss["grade_rule"]
    with st.expander("등급 분류 기준 (임시 — 추가 정의 필요)", expanded=True):
        c1, c2, c3 = st.columns(3)
        rule["repeat"] = c1.number_input("재방문: 방문 횟수 ≥", 2, 50, rule["repeat"])
        rule["regular"] = c2.number_input("단골: 방문 횟수 ≥", rule["repeat"] + 1, 100, max(rule["regular"], rule["repeat"] + 1))
        rule["dormant"] = c3.number_input("휴면: 마지막 방문 후 N일 이상", 7, 365, rule["dormant"])
        st.caption("그 외(방문 1회)는 신규 고객입니다. 이 값은 화면에서 미리 보는 용도이고 서버에는 저장되지 않아요.")
    cust = repo.members(rule)
    kpi_row(*[kpi(f"{g} 고객", int((cust["등급"] == g).sum()), "명") for g in GRADES])
    st.html('<div style="height:16px"></div>')
    pick = st.multiselect("등급 필터", GRADES, default=GRADES)
    st.dataframe(cust[cust["등급"].isin(pick)], hide_index=True, width="stretch")


def page_orders(repo):
    page_head("주문 이력", "들어온 주문을 전체 또는 고객별로 확인해요")
    orders = repo.orders()
    cust = repo.members(ss["grade_rule"]).set_index("customer_id")
    mode = st.radio("보기", ["전체 주문", "고객별 주문"], horizontal=True)
    if mode == "고객별 주문":
        if cust.empty:
            st.info("아직 회원이 없어요.")
            return
        who = st.selectbox("고객", cust.index, format_func=lambda i: f"{cust.at[i, '닉네임']} ({i}) · {cust.at[i, '등급']}")
        orders = orders[orders["customer_id"] == who]
        kpi_row(kpi("누적 주문 금액", f"{int(orders['금액'].sum()):,}", "원"))
        st.html('<div style="height:16px"></div>')
    st.dataframe(orders, hide_index=True, width="stretch",
                 column_config={"금액": st.column_config.NumberColumn(format="%d원")})


def page_marketing(repo):
    page_head("마케팅", "수신 동의한 회원에게 문자를 보내 재방문을 이끌어요")
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
    kpi_row(kpi("이번 달 SMS", f"{usage['used']['SMS']} / {usage['limit']['SMS']}", "건"),
            kpi("이번 달 LMS", f"{usage['used']['LMS']} / {usage['limit']['LMS']}", "건"))
    st.html('<div style="height:16px"></div>')

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
        sec_title("발송 내역")
        st.dataframe(pd.DataFrame(logs)[["ts", "type", "status", "target_count", "request_id", "error", "content"]],
                     hide_index=True, width="stretch")


if not ss["owner"]:
    login()
    st.stop()

repo = ss["repo"]
store = repo.backend.store()
with st.sidebar:
    st.html(f'<div class="sb-brand"><div class="sb-logo">🍺</div><div><div class="sb-name">식당도우미</div>'
            f'<div class="sb-sub">관리자 콘솔</div></div></div><div class="sb-label">MENU</div>')
    page = st.radio("메뉴", PAGES, label_visibility="collapsed")
    st.html('<div style="height:18px"></div><div class="sb-label">STORE</div>')
    st.caption(f"{store['name']} {store['branch']} · OWNER")
    st.caption("🟢 서버 데이터" if repo.source == "api" else "🧪 더미 데이터")
    st.html('<div style="height:10px"></div>')
    if st.button("로그아웃"):
        ss["owner"], ss["repo"] = False, None
        st.rerun()
if ss["notice"]:
    st.warning(ss["notice"])

{"대시보드": page_dashboard, "메뉴 관리": page_menu, "추천 가중치": page_weights, "고객 등급": page_customers,
 "주문 이력": page_orders, "마케팅": page_marketing}[page](repo)
