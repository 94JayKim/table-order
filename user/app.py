"""티오더 스타일 테이블 오더 - 역전할머니맥주 (Streamlit 데모)

실행: streamlit run app.py
"""
import random
import time
from datetime import datetime
from pathlib import Path
from html import escape

import streamlit as st
from PIL import Image

import login_demo

from menu_data import (CATEGORIES, CATEGORY_BY_ID, MENU, MENU_BY_ID, PROMOS,
                       ROULETTE_PRIZES, STAFF_CALLS, STORE)
from recommendations import DISCOUNT_PERCENT, combo_cart_line, recommend_combos

st.set_page_config(page_title=f"{STORE['name']} 테이블오더", page_icon="🍺",
                   layout="wide", initial_sidebar_state="collapsed")

# ============================== 상태 ==============================
def init_state():
    ss = st.session_state
    ss.setdefault("page", "splash")
    ss.setdefault("cat", "best")
    ss.setdefault("cart", {})        # key -> {id, name, opt, unit, qty}
    ss.setdefault("orders", [])      # 주문 내역
    ss.setdefault("calls", [])
    ss.setdefault("table", 12)
    ss.setdefault("roulette", None)  # {"idx", "angle", "animate"} - 세션당 1회
    ss.setdefault("roulette_percent", 0)  # 다음 주문에 적용할 룰렛 할인율
    ss.setdefault("member", None)    # QR 로그인한 회원 (더미)
    ss.setdefault("bonus_spin_used", False)
    ss.setdefault("login", login_demo.new_session(time.time()))


def cart_add(item, opt_label, unit, qty):
    cart = st.session_state.cart
    key = f"{item['id']}|{opt_label}"
    if key in cart:
        cart[key]["qty"] += qty
    else:
        cart[key] = {"id": item["id"], "name": item["name"], "opt": opt_label, "unit": unit, "qty": qty}


def cart_change(key, delta):
    line = st.session_state.cart.get(key)
    if not line:
        return
    line["qty"] += delta
    if line["qty"] <= 0:
        del st.session_state.cart[key]


def cart_remove(key):
    st.session_state.cart.pop(key, None)


def cart_subtotal():
    return sum(l["unit"] * l["qty"] for l in st.session_state.cart.values())


def roulette_discount():
    return cart_subtotal() * st.session_state.roulette_percent // 100 // 10 * 10


def cart_total():
    return cart_subtotal() - roulette_discount()


def cart_count(item_id=None):
    if item_id is None:
        return sum(l["qty"] for l in st.session_state.cart.values())
    return sum(l["qty"] * (sum(c["qty"] for c in l["components"] if c["id"] == item_id)
                           if "components" in l else int(l["id"] == item_id))
               for l in st.session_state.cart.values())


def cart_discount():
    return sum((line.get("original_unit", line["unit"]) - line["unit"]) * line["qty"]
               for line in st.session_state.cart.values())


def add_combo(combo):
    if any(MENU_BY_ID[c["id"]]["soldout"] for c in combo["components"]):
        st.toast("품절된 메뉴가 있어 다른 조합을 선택해 주세요.", icon="🙏")
        return
    key, line = combo_cart_line(combo)
    if key in st.session_state.cart:
        st.session_state.cart[key]["qty"] += 1
    else:
        st.session_state.cart[key] = line


def won(n):
    return f"{n:,}원"


def go(page):
    st.session_state.page = page


# ============================== 다이얼로그 ==============================
def thumb_html(item, qty_in_cart=0, big=False):
    c1, c2 = CATEGORY_BY_ID[item["cat"]][3]
    size = " big" if big else ""
    badges = ""
    for t in item["tags"]:
        badges += '<span class="badge spicy">🌶 매운맛</span>' if t == "매운맛" else f'<span class="badge {t}">{t}</span>'
    extra = f'<div class="incart">{qty_in_cart}개 담김</div>' if qty_in_cart else ""
    sold = '<div class="soldout">품절</div>' if item["soldout"] else ""
    return (f'<div class="thumb{size}" style="background:linear-gradient(135deg,{c1},{c2})">'
            f'{item["emoji"]}<div class="badges">{badges}</div>{extra}{sold}</div>')


@st.dialog("주문 확인", width="medium")
def confirm_dialog():
    cart = st.session_state.cart
    for l in cart.values():
        opt = f" ({l['opt']})" if l["opt"] else ""
        st.html(f'<div class="order-item"><span>{l["name"]}{opt} × {l["qty"]}</span>'
                    f'<span>{won(l["unit"] * l["qty"])}</span></div>')
    st.divider()
    if cart_discount():
        st.caption(f"AI 조합 할인 −{won(cart_discount())} 적용")
    if roulette_discount():
        st.caption(f"룰렛 {st.session_state.roulette_percent}% 할인 −{won(roulette_discount())} 적용")
    st.html(f'<div class="total-row"><span>총 주문금액</span><b>{won(cart_total())}</b></div>')
    st.caption("주문 후에는 취소가 어려우니 직원에게 문의해 주세요.")
    with st.container(key="dialog_actions"):
        c1, c2 = st.columns(2, wrap=False)
    if c1.button("돌아가기", width="stretch"):
        st.rerun()
    if c2.button("주문하기", type="primary", width="stretch"):
        no = len(st.session_state.orders) + 1
        st.session_state.orders.append({"no": no, "ts": time.time(), "time": datetime.now().strftime("%H:%M"),
                                        "lines": list(cart.values()), "total": cart_total()})
        st.session_state.cart = {}
        st.session_state.roulette_percent = 0
        st.toast(f"주문이 접수되었습니다 (주문번호 #{no})", icon="✅")
        st.rerun()


@st.dialog("주문내역", width="large")
def orders_dialog():
    orders = st.session_state.orders
    if not orders:
        st.html('<div class="cart-empty">아직 주문 내역이 없어요</div>')
        return
    for o in reversed(orders):
        elapsed = time.time() - o["ts"]
        s, label = (0, "접수완료") if elapsed < 15 else (1, "조리중") if elapsed < 45 else (2, "서빙완료")
        rows = "".join(
            f'<div class="order-item"><span>{l["name"]}{" (" + l["opt"] + ")" if l["opt"] else ""} × {l["qty"]}</span>'
            f'<span>{won(l["unit"] * l["qty"])}</span></div>' for l in o["lines"])
        st.html(f'<div class="order-box"><div class="order-head"><span>주문 #{o["no"]} · {o["time"]}</span>'
                    f'<span class="status s{s}">{label}</span></div>{rows}'
                    f'<div class="order-item" style="margin-top:6px;font-weight:800;color:#ffb703"><span>소계</span><span>{won(o["total"])}</span></div></div>')
    st.html(f'<div class="total-row"><span>누적 주문금액</span><b>{won(sum(o["total"] for o in orders))}</b></div>')
    st.caption("※ 데모: 시간이 지나면 주문 상태가 자동으로 바뀝니다. 새로 열면 갱신돼요.")


@st.dialog("직원 호출", width="medium")
def staff_dialog():
    picks = st.pills("필요한 항목을 선택해 주세요", STAFF_CALLS, selection_mode="multi")
    if st.button("호출하기", type="primary", width="stretch", disabled=not picks):
        st.session_state.calls.append((datetime.now().strftime("%H:%M"), picks))
        st.toast("직원이 곧 도착합니다 🙋", icon="🔔")
        st.rerun()


@st.dialog("장바구니", width="medium", on_dismiss="rerun")
def cart_dialog():
    render_cart(dialog=True)


# ============================== 룰렛 ==============================
def spin_roulette():
    ss = st.session_state
    if ss.roulette:
        return
    idx = random.randrange(len(ROULETTE_PRIZES))
    seg = 360 / len(ROULETTE_PRIZES)
    # 포인터(12시 방향) 아래에 당첨 칸의 중앙 부근이 오도록 회전
    angle = 360 * 5 - (idx * seg + random.uniform(-seg * 0.3, seg * 0.3))
    ss.roulette = {"idx": idx, "angle": round(angle, 1), "animate": True}
    prize = ROULETTE_PRIZES[idx]
    if prize["kind"] == "discount":
        ss.roulette_percent = prize["percent"]
    else:
        item = MENU_BY_ID[prize["item_id"]]
        cart_add(item, "룰렛 서비스", 0, 1)


CONFETTI = [(18, 18, 38, 12, "#f1566f", -35), (3, 40, 14, 14, "#5b8def", 20), (84, 6, 34, 11, "#37b36b", 30),
            (90, 40, 16, 16, "#9b6bd6", 10), (5, 70, 30, 10, "#2f8de0", 35), (96, 66, 24, 9, "#ffc933", 20)]


@st.cache_resource
def qr_png(seed: int = 7):
    """데모용 가짜 QR 이미지 (실제 스캔 불가). 로그인 토큰마다 모양이 달라진다."""
    rnd, n, scale = random.Random(seed), 25, 8
    img = Image.new("RGB", (n * scale, n * scale), "white")
    px = img.load()
    for r in range(n):
        for c in range(n):
            fr, fc = (r % 18 if r >= 18 else r), (c % 18 if c >= 18 else c)
            if (r < 7 or r >= 18) and (c < 7 or c >= 18) and not (r >= 18 and c >= 18):
                on = fr in (0, 6) or fc in (0, 6) or (2 <= fr <= 4 and 2 <= fc <= 4)
            else:
                on = rnd.random() < .5
            if on:
                for y in range(r * scale, (r + 1) * scale):
                    for x in range(c * scale, (c + 1) * scale):
                        px[x, y] = (17, 17, 17)
    return img


def render_roulette():
    ss = st.session_state
    prizes, spun = ROULETTE_PRIZES, ss.roulette
    n = len(prizes)
    seg = 360 / n
    gap = 1.2
    stops = ",".join(f'{p["color"]} {i * seg}deg {(i + 1) * seg - gap}deg,#fff {(i + 1) * seg - gap}deg {(i + 1) * seg}deg'
                     for i, p in enumerate(prizes))
    labels = "".join(
        f'<div class="rw-label" style="transform:rotate({i * seg}deg)"><span style="transform:rotate({-i * seg}deg)">'
        f'{p["label"]}<em>{p["emoji"]}</em></span></div>' for i, p in enumerate(prizes))
    dots = "".join(f'<div class="rw-dot" style="transform:rotate({k * 360 / 16}deg)"><i></i></div>' for k in range(16))
    conf = "".join(f'<div class="rw-conf" style="left:{x}%;top:{y}%;width:{w}px;height:{h}px;background:{col};transform:rotate({r}deg)"></div>'
                   for x, y, w, h, col, r in CONFETTI)
    cls = " spin" if spun and spun["animate"] else ""
    to = f'--to:{spun["angle"]}deg;' if spun else ""
    st.html('<div class="rw-title"><div class="fork">🍴</div>'
            '<div class="q">오늘, 어떤 메뉴가 좋을까요?</div>'
            '<h2><i class="l1"></i><i class="l2"></i>행운의 <span>룰렛</span>을 돌려보세요!<i class="r1"></i><i class="r2"></i></h2>'
            '<div class="s">맛있는 식사와 함께 작은 행운도 받아가세요!</div></div>')
    with st.container(key="rw_box"):
        st.html('<div class="rw-stage"><div class="rw-stand"></div><div class="rw-ring"></div>'
                f'{dots}<div class="rw-pin"></div>'
                f'<div class="rw-wheel{cls}" style="{to}background:conic-gradient(from {-seg / 2}deg,{stops})">{labels}</div>'
                f'{conf}<div class="rw-star" style="left:-8%;top:10%">⭐</div><div class="rw-star" style="right:-9%;top:28%">⭐</div>'
                '<div class="rw-bubble l">오늘의<br>작은 행운!<br>어떤 선물이<br>기다리고 있을까요?</div>'
                '<div class="rw-bubble r">맛있는 식사와<br>특별한 혜택을<br>함께! <span class="heart">♥</span></div></div>')
        with st.container(key="rw_start"):
            st.button("START", type="primary", key="roulette_btn", disabled=bool(spun), on_click=spin_roulette)
    if spun:
        prize = prizes[spun["idx"]]
        note = "다음 주문에 자동 적용돼요" if prize["kind"] == "discount" else "장바구니에 담아 두었어요"
        reveal = " reveal" if spun["animate"] else ""
        st.html(f'<div class="rw-result{reveal}"><div class="t">축하합니다! 오늘의 행운은</div>'
                f'<div class="p">{prize["emoji"]} {prize["short"]}</div><div class="n">{note}</div></div>')
        spun["animate"] = False


# ============================== 화면 ==============================
def finish_login():
    """로그인 세션이 승인되면 회원 정보를 반영하고, 룰렛을 한 번 더 돌릴 수 있게 한다."""
    ss = st.session_state
    if ss.member or login_demo.state(ss.login, time.time()) != "logged_in":
        return False
    ss.member = ss.login["member"]
    if ss.roulette and not ss.bonus_spin_used:
        ss.roulette = None
        ss.bonus_spin_used = True
    return True


def login_action(action):
    ss = st.session_state
    now = time.time()
    if action == "scan":
        login_demo.scan(ss.login, now)
    elif action == "approve":
        login_demo.approve(ss.login, now, {"nickname": ss.get("demo_nick") or "카카오", "kakao_id": "demo"})
    elif action == "expire":
        ss.login["created"] -= login_demo.TTL_SECONDS + 1
    elif action == "refresh":
        ss.login = login_demo.new_session(now)


@st.fragment(run_every=2)
def login_demo_panel():
    """서버가 보내는 로그인 상태를 주기적으로 확인하는 부분 (정식 구현은 WebSocket)."""
    ss = st.session_state
    if finish_login():
        st.rerun()
    now = time.time()
    status = login_demo.state(ss.login, now)
    label = {"waiting": "휴대폰 스캔 대기 중", "scanned": "카카오 로그인 대기 중",
             "expired": "QR이 만료되었어요", "logged_in": "로그인 완료"}[status]
    st.caption(f"상태: **{label}** · 남은 시간 {login_demo.remaining(ss.login, now)}초 · 토큰 `{ss.login['token']}`")
    st.text_input("카카오 닉네임 (데모)", "카카오", key="demo_nick")
    c1, c2, c3, c4 = st.columns(4)
    c1.button("① 휴대폰 QR 스캔", key="login_scan", width="stretch", disabled=status != "waiting",
              on_click=login_action, args=("scan",))
    c2.button("② 카카오 로그인", key="login_approve", width="stretch", disabled=status != "scanned",
              on_click=login_action, args=("approve",))
    c3.button("만료시키기", key="login_expire", width="stretch", on_click=login_action, args=("expire",))
    c4.button("QR 새로고침", key="login_refresh", width="stretch", type="primary" if status == "expired" else "secondary",
              on_click=login_action, args=("refresh",))


def render_splash():
    render_roulette()
    member = st.session_state.member
    with st.container(horizontal=True, key="splash_bottom"):
        with st.container(horizontal=True, key="qr_card"):
            if member:
                st.html(f'<div class="qr-text"><div class="a">{escape(member["nickname"])}님</div>'
                        '<div class="b">로그인 완료!</div><div class="c">룰렛 한 번 더 돌릴 수 있어요.</div></div>')
            else:
                token = st.session_state.login["token"]
                st.image(qr_png(int(token, 16) % 2**31), width=96)
                st.html('<div class="qr-text"><div class="a">회원가입하고</div><div class="b">룰렛 한번 더!</div>'
                        '<div class="c">QR코드를 스캔하여<br>간단하게 가입하고<br>추가 기회를 받아보세요!</div></div>')
        with st.container(key="start_cta"):
            st.button("🍴 메뉴선택  ›", type="primary", width="stretch", key="start_btn", on_click=go, args=("menu",))
    if not member:
        with st.expander("🧪 데모: 휴대폰 로그인 시뮬레이션 (정식 구현 시 제거)"):
            st.caption(f"QR 주소 예시: https://example.com/m/login?t={st.session_state.login['token']} — 실제 QR이 아닙니다.")
            login_demo_panel()


def render_header():
    with st.container(key="header"):
        c_brand, c_table, c_actions = st.columns([3.5, 1.2, 4], vertical_alignment="center")
        c_brand.html(f'<div class="brand"><div class="logo">🍺</div><div><div class="name">{STORE["name"]}</div>'
                     f'<div class="sub">{STORE["branch"]}{f" · {escape(st.session_state.member["nickname"])}님" if st.session_state.member else ""}</div></div></div>')
        c_table.html(f'<div class="table-chip">TABLE <b>{st.session_state.table}</b></div>')
        with c_actions.container(horizontal=True, key="header_actions"):
            if st.button("🔔 직원호출", width="stretch"):
                staff_dialog()
            n_orders = len(st.session_state.orders)
            if st.button(f"🧾 주문내역{f' ({n_orders})' if n_orders else ''}", width="stretch"):
                orders_dialog()
            if st.button(f"🛒 장바구니 ({cart_count()})", width="stretch"):
                cart_dialog()
            st.button("🏠 처음으로", width="stretch", on_click=go, args=("splash",))


def render_categories():
    for cid, icon, name, _ in CATEGORIES:
        if st.button(f"{icon}  {name}", key=f"cat_{cid}", width="stretch",
                     type="primary" if st.session_state.cat == cid else "secondary"):
            st.session_state.cat = cid
            st.rerun()


def render_menu():
    cat = st.session_state.cat
    if cat == "ai":
        render_recommendations()
        return
    items = [m for m in MENU if "BEST" in m["tags"]] if cat == "best" else [m for m in MENU if m["cat"] == cat]
    _, icon, name, _ = CATEGORY_BY_ID[cat]
    st.html(f'<div class="section-title">{icon} {name} <span>{len(items)}</span></div>')
    with st.container(horizontal=True, key="menu_grid"):
        for item in items:
            with st.container(key=f"card_{item['id']}"):
                st.html(thumb_html(item, cart_count(item["id"])) +
                        f'<div class="mname">{item["name"]}</div><div class="mdesc">{item["desc"]}</div>'
                        f'<div class="mprice">{won(item["price"])}</div>')
                if st.button("품절" if item["soldout"] else "담기", key=f"add_{item['id']}", width="stretch",
                             disabled=item["soldout"]):
                    cart_add(item, "", item["price"], 1)
                    st.rerun()


def render_recommendations():
    st.html('<div class="ai-hero"><div class="ai-eyebrow">✨ 오늘의 맞춤 메뉴</div>'
            '<h2>AI 추천 조합</h2><p>취향에 맞는 한 상, 조합 할인까지 한 번에.</p>'
            f'<span class="ai-offer">조합으로 주문하면 {DISCOUNT_PERCENT}% 할인</span></div>')
    with st.container(key="ai_preferences"):
        st.html('<div class="ai-preference-title">어떤 한 상을 원하세요?</div>')
        with st.container(key="ai_preference_fields"):
            c1, c2, c3, c4 = st.columns(4, wrap=False)
            people = c1.selectbox("주문 인원", list(range(1, 7)), index=1,
                                  format_func=lambda n: f"{n}명", key="ai_people")
            budget = c2.selectbox("조합 예산", [20000, 30000, 40000, 60000, 100000], index=2,
                                  format_func=lambda n: f"{won(n)} 이하", key="ai_budget")
            spicy = c3.selectbox("맵기 취향", ["상관없어요", "맵지 않게", "매콤하게"], key="ai_spicy")
            drink = c4.selectbox("함께 마실 음료", ["맥주", "소주", "음료", "없이"], key="ai_drink")
        st.caption("선택한 조건에 따라 추천이 바로 바뀝니다. 예산은 한 조합의 할인 후 총액 기준입니다.")
    lines = list(st.session_state.cart.values()) + [line for order in st.session_state.orders for line in order["lines"]]
    combos = recommend_combos(people, budget, spicy, drink, lines)
    st.html(f'<div class="section-title ai-results-title">나에게 맞는 추천 <span>{len(combos)}</span>'
            f'<small>{people}명 · {won(budget)} 이하</small></div>')
    if not combos:
        st.info("선택한 조건에 맞는 조합이 없어요. 예산을 높이거나 음료·인원 조건을 바꿔 주세요.")
    for rank, combo in enumerate(combos, 1):
        with st.container(key=f"ai_combo_{rank}"):
            contents = "".join(
                f'<div class="combo-item"><span class="combo-emoji">{c["emoji"]}</span>'
                f'<span>{escape(c["name"])}<small>{escape(c["opt"])}</small></span><b>× {c["qty"]}</b></div>'
                for c in combo["components"])
            st.html(f'<div class="combo-heading"><span class="combo-rank rank-{rank}">{rank}위</span>'
                    f'<h3>{combo["name"]}</h3>{"<span class=\"combo-top\">가장 추천해요</span>" if rank == 1 else ""}</div>'
                    f'<div class="combo-items">{contents}</div>'
                    f'<div class="combo-reason"><strong>✨ 이 조합을 추천한 이유</strong><p>{combo["reason"]}</p></div>'
                    f'<div class="combo-pricing"><span class="combo-discount">{DISCOUNT_PERCENT}% 할인</span>'
                    f'<del>{won(combo["original"])}</del><strong>{won(combo["price"])}</strong>'
                    f'<small>{won(combo["discount"])} 절약</small></div>')
            if st.button(f"{rank}위 조합 담기 · {won(combo['price'])}", key=f"add_combo_{rank}",
                         type="primary" if rank == 1 else "secondary", width="stretch"):
                add_combo(combo)
                st.toast("할인된 가격으로 조합을 담았어요", icon="🛒")
                st.rerun()
    st.caption("현재는 취향과 주문 정보를 반영한 데모 추천입니다. 조합 할인은 세트 단위로 적용됩니다.")


def render_cart(dialog=False):
    cart = st.session_state.cart
    with st.container(key="dialog_cart_panel" if dialog else "cart_panel"):
        st.html(f'<div class="cart-title">🛒 장바구니 <span>{cart_count()}</span></div>')
        with st.container(key="dialog_cart_items" if dialog else "cart_items"):
            if not cart:
                st.html('<div class="cart-empty"><span class="emoji">🍻</span>메뉴를 담아주세요</div>')
            for key, l in list(cart.items()):
                st.html(f'<div class="cart-line"><div><div class="n">{l["name"]}</div>'
                            f'<div class="o">{l["opt"]}</div></div><div class="p">{won(l["unit"] * l["qty"])}</div></div>')
                c1, c2, c3, c4 = st.columns(4, vertical_alignment="center", wrap=False)
                prefix = "dialog_" if dialog else ""
                c1.button("−", key=f"q_{prefix}dec_{key}", help=f"{l['name']} 수량 줄이기", width="stretch", on_click=cart_change, args=(key, -1))
                c2.html(f'<div class="quantity">{l["qty"]}</div>')
                c3.button("+", key=f"q_{prefix}inc_{key}", help=f"{l['name']} 수량 늘리기", width="stretch", on_click=cart_change, args=(key, 1))
                c4.button("🗑", key=f"q_{prefix}del_{key}", help=f"{l['name']} 삭제", width="stretch", on_click=cart_remove, args=(key,))
                st.divider()
        if cart_discount():
            st.html(f'<div class="cart-savings">✨ AI 조합으로 {won(cart_discount())} 할인받았어요</div>')
        if roulette_discount():
            st.html(f'<div class="cart-savings">🎟️ 룰렛 {st.session_state.roulette_percent}% 할인 −{won(roulette_discount())}</div>')
        st.html(f'<div class="total-row"><span>총 주문금액</span><b>{won(cart_total())}</b></div>')
        if st.button("주문 확인하기", type="primary", width="stretch", key="dialog_order_btn" if dialog else "order_btn", disabled=not cart):
            st.session_state.confirm_order = True
            st.rerun()


def main():
    init_state()
    st.html(Path(__file__).with_name("app.css"))
    if st.session_state.page == "splash":
        render_splash()
        return
    render_header()
    with st.container(key="order_layout"):
        c_cat, c_menu, c_cart = st.columns([1.15, 5.2, 2.5], gap="medium")
    with c_cat:
        with st.container(key="categories"):
            render_categories()
    with c_menu:
        render_menu()
    with c_cart:
        render_cart()
    if st.session_state.pop("confirm_order", False):
        confirm_dialog()


main()
