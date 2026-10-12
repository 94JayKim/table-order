"""관리자(OWNER) 페이지: streamlit run admin/app.py --server.port 8502

1차 Prototype 설계 회의록 기준. 모든 데이터는 더미이며 서버와 연결되지 않는다.
"""

import os

import pandas as pd
import streamlit as st

from dummy_data import (AGE_GROUPS, GRADES, SPICY_LABELS, TODAY, make_customers,
                        make_orders, menu_frame)
from menu_data import CATEGORIES, STORE

st.set_page_config(page_title="식당도우미 관리자", page_icon="🛠️", layout="wide")

OWNER_PASSWORD = os.getenv("ADMIN_PASSWORD", "owner")  # 데모용. 실제 인증은 서버에서.
PAGES = ["대시보드", "메뉴 관리", "추천 가중치", "고객 등급", "주문 이력", "마케팅"]
CAT_NAMES = [c[2] for c in CATEGORIES if c[0] != "ai"]

ss = st.session_state
ss.setdefault("owner", False)
ss.setdefault("menu", menu_frame())
ss.setdefault("customers", make_customers())
ss.setdefault("grade_rule", {"repeat": 2, "regular": 5, "dormant": 60})
ss.setdefault("campaigns", [])
ss.setdefault("orders", make_orders(ss["customers"]))


def grade_of(row) -> str:
    rule = ss["grade_rule"]
    if (TODAY - row["마지막 방문일"]).days >= rule["dormant"]:
        return "휴면"
    if row["방문 횟수"] >= rule["regular"]:
        return "단골"
    if row["방문 횟수"] >= rule["repeat"]:
        return "재방문"
    return "신규"


def customers_graded() -> pd.DataFrame:
    df = ss["customers"].copy()
    df["등급"] = df.apply(grade_of, axis=1)
    return df


def login():
    st.title("🛠️ 식당도우미 관리자")
    st.caption("OWNER(사장님)만 접근할 수 있습니다. MANAGER·STAFF 권한은 1차 Prototype에서 사용하지 않습니다.")
    pw = st.text_input("OWNER 비밀번호", type="password")
    if st.button("로그인", type="primary"):
        if pw == OWNER_PASSWORD:
            ss["owner"] = True
            st.rerun()
        st.error("비밀번호가 올바르지 않습니다.")
    st.info("데모 비밀번호는 `owner` 입니다. (환경변수 ADMIN_PASSWORD로 변경)")


def page_dashboard():
    orders = ss["orders"]
    today = orders[orders["주문 시각"].dt.date == TODAY]
    cust = customers_graded()
    visited_today = set(today["customer_id"])
    today_c = cust[cust["customer_id"].isin(visited_today)]

    st.subheader("주문 통계")
    a, b, c, d = st.columns(4)
    a.metric("오늘 주문 수", f"{len(today)}건")
    b.metric("평균 주문금액", f"{int(today['금액'].mean()):,}원" if len(today) else "-")
    c.metric("오늘 신규 고객", f"{(today_c['등급'] == '신규').sum()}명")
    d.metric("오늘 재방문 고객", f"{(today_c['등급'].isin(['재방문', '단골'])).sum()}명")

    st.subheader("고객 분석")
    l, r = st.columns(2)
    with l:
        st.caption("고객 연령대")
        st.bar_chart(cust["연령대"].value_counts().reindex(AGE_GROUPS).fillna(0))
    with r:
        st.caption("고객 성별")
        st.bar_chart(cust["성별"].value_counts())

    l, r = st.columns(2)
    with l:
        st.subheader("인기 메뉴 TOP 10")
        counts: dict[str, int] = {}
        for line in orders["주문 내역"]:
            for part in line.split(", "):
                name, _, qty = part.rpartition(" x")
                counts[name] = counts.get(name, 0) + int(qty)
        top = pd.Series(counts).sort_values(ascending=False).head(10)
        st.bar_chart(top, horizontal=True)
    with r:
        st.subheader("AI 추천 분석")
        ai = orders[orders["AI 추천 사용"]]
        shown = len(orders) * 2  # 더미: 추천 노출 수
        st.metric("AI 추천 적중률", f"{len(ai) / shown:.0%}")
        st.caption("임시 기준: 추천 조합 노출 대비 실제 주문으로 이어진 비율. "
                   "정확한 계산 기준은 추가 정의가 필요합니다.")
        st.metric("AI 추천으로 들어온 주문", f"{len(ai)}건 / 전체 {len(orders)}건")


def page_menu():
    st.subheader("메뉴 관리")
    st.caption("메뉴명·가격·설명·이미지·판매 여부·매운 정도·카테고리·추천 가중치·세트 가능 여부를 수정합니다.")
    edited = st.data_editor(
        ss["menu"], hide_index=True, width="stretch", num_rows="dynamic",
        disabled=["id"], height=520,
        column_config={
            "카테고리": st.column_config.SelectboxColumn(options=CAT_NAMES, required=True),
            "가격": st.column_config.NumberColumn(min_value=0, step=500, format="%d원"),
            "매운 정도": st.column_config.SelectboxColumn(options=list(SPICY_LABELS.values())),
            "추천 가중치": st.column_config.NumberColumn(min_value=0, max_value=100, step=5),
            "이미지 URL": st.column_config.LinkColumn(),
            "판매 여부": st.column_config.CheckboxColumn(),
            "세트 가능": st.column_config.CheckboxColumn(),
        },
    )
    if st.button("저장", type="primary"):
        ss["menu"] = edited.reset_index(drop=True)
        st.success("저장했습니다. (데모: 세션 안에서만 유지)")


def page_weights():
    st.subheader("OWNER 추천 가중치")
    st.caption("0~100. 높을수록 AI 추천 조합에 우선 반영됩니다. 50이 기본값입니다.")
    menu = ss["menu"]
    cat = st.selectbox("카테고리", ["전체"] + CAT_NAMES)
    view = menu if cat == "전체" else menu[menu["카테고리"] == cat]
    for idx, row in view.iterrows():
        c1, c2 = st.columns([2, 3])
        c1.write(f"**{row['메뉴명']}**" + ("" if row["판매 여부"] else " (품절)"))
        menu.at[idx, "추천 가중치"] = c2.slider(
            row["메뉴명"], 0, 100, int(row["추천 가중치"]), 5,
            key=f"w_{row['id']}", label_visibility="collapsed")
    ss["menu"] = menu


def page_customers():
    st.subheader("고객 등급 관리")
    rule = ss["grade_rule"]
    with st.expander("등급 분류 기준 (임시 — 추가 정의 필요)", expanded=True):
        c1, c2, c3 = st.columns(3)
        rule["repeat"] = c1.number_input("재방문: 방문 횟수 ≥", 2, 50, rule["repeat"])
        rule["regular"] = c2.number_input("단골: 방문 횟수 ≥", rule["repeat"] + 1, 100, max(rule["regular"], rule["repeat"] + 1))
        rule["dormant"] = c3.number_input("휴면: 마지막 방문 후 N일 이상", 7, 365, rule["dormant"])
        st.caption("그 외(방문 1회)는 신규 고객입니다.")
    cust = customers_graded()
    cols = st.columns(4)
    for col, g in zip(cols, GRADES):
        col.metric(f"{g} 고객", f"{(cust['등급'] == g).sum()}명")
    pick = st.multiselect("등급 필터", GRADES, default=GRADES)
    st.dataframe(cust[cust["등급"].isin(pick)], hide_index=True, width="stretch")


def page_orders():
    st.subheader("주문 이력")
    cust = customers_graded().set_index("customer_id")
    orders = ss["orders"].copy()
    orders["닉네임"] = orders["customer_id"].map(cust["닉네임"])
    mode = st.radio("보기", ["전체 주문", "고객별 주문"], horizontal=True)
    if mode == "고객별 주문":
        who = st.selectbox("고객", cust.index, format_func=lambda i: f"{cust.at[i, '닉네임']} ({i}) · {cust.at[i, '등급']}")
        orders = orders[orders["customer_id"] == who]
        st.metric("누적 주문 금액", f"{int(orders['금액'].sum()):,}원")
    st.dataframe(orders, hide_index=True, width="stretch",
                 column_config={"금액": st.column_config.NumberColumn(format="%d원")})


def page_marketing():
    st.subheader("마케팅 지원")
    cust = customers_graded()
    st.caption("우선순위: 카카오톡·문자 발송 → Redis 알림(후순위, 미구현). 수신 동의 고객에게만 발송됩니다.")
    grades = st.multiselect("대상 등급", GRADES, default=["휴면"])
    channel = st.radio("채널", ["카카오톡", "문자(SMS)"], horizontal=True)
    msg = st.text_area("메시지", f"[{STORE['name']}] 오랜만이에요! 이번 주 방문하시면 안주 10% 할인해 드려요 🍺")
    targets = cust[cust["등급"].isin(grades) & cust["마케팅 수신 동의"]]
    st.info(f"발송 대상: **{len(targets)}명** (선택 등급 {int(cust['등급'].isin(grades).sum())}명 중 수신 동의자)")
    if st.button("발송 (데모)", type="primary", disabled=targets.empty or not msg.strip()):
        ss["campaigns"].insert(0, {"채널": channel, "대상 등급": ", ".join(grades),
                                   "발송 수": len(targets), "메시지": msg})
        st.success("발송 처리했습니다. 실제 메시지는 전송되지 않습니다.")
    if ss["campaigns"]:
        st.write("발송 내역")
        st.dataframe(pd.DataFrame(ss["campaigns"]), hide_index=True, width="stretch")


if not ss["owner"]:
    login()
    st.stop()

with st.sidebar:
    st.title("🛠️ 관리자")
    st.caption(f"{STORE['name']} {STORE['branch']} · OWNER")
    page = st.radio("메뉴", PAGES, label_visibility="collapsed")
    if st.button("로그아웃"):
        ss["owner"] = False
        st.rerun()

{"대시보드": page_dashboard, "메뉴 관리": page_menu, "추천 가중치": page_weights,
 "고객 등급": page_customers, "주문 이력": page_orders, "마케팅": page_marketing}[page]()
