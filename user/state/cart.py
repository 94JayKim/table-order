"""장바구니 상태와 금액 계산.
"""

import streamlit as st

from recommendations import combo_cart_line
from user.state import context as ctx


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
    if any(ctx.MENU_BY_ID[c["id"]]["soldout"] for c in combo["components"]):
        st.toast("품절된 메뉴가 있어 다른 조합을 선택해 주세요.", icon="🙏")
        return
    key, line = combo_cart_line(combo)
    if key in st.session_state.cart:
        st.session_state.cart[key]["qty"] += 1
    else:
        st.session_state.cart[key] = line
