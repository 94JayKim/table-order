"""주문 화면의 조각 (상단 헤더·카테고리·메뉴 목록).
"""

from html import escape

import streamlit as st

from user.state import context as ctx
from user.state.cart import cart_add, cart_count
from user.state.quiz import open_quiz
from user.ui.common import mini_buttons, thumb_html, won
from user.ui.dialogs import cart_dialog, orders_dialog, staff_dialog
from user.views.ai import render_recommendations


def render_header():
    with st.container(key="header"):
        c_brand, c_table, c_actions, c_mini = st.columns([3.5, 1.2, 3, 1], vertical_alignment="center")
        c_brand.html(f'<div class="brand"><div class="logo">🍺</div><div><div class="name">{ctx.STORE["name"]}</div>'
                     f'<div class="sub">{ctx.STORE["branch"]}{f" · {escape(st.session_state.member["nickname"])}님 (회원)" if st.session_state.member else " · 비회원"}</div></div></div>')
        c_table.html(f'<div class="table-chip">TABLE <b>{st.session_state.table}</b></div>')
        with c_actions.container(horizontal=True, key="header_actions"):
            if st.button("🔔 직원호출", width="stretch"):
                staff_dialog()
            n_orders = len(st.session_state.orders)
            if st.button(f"🧾 주문내역{f' ({n_orders})' if n_orders else ''}", width="stretch"):
                orders_dialog()
            if st.button(f"🛒 장바구니 ({cart_count()})", width="stretch"):
                cart_dialog()
        with c_mini:
            mini_buttons("header")


def render_categories():
    st.button("💬 AI 질문", key="open_quiz", width="stretch", type="primary", on_click=open_quiz,
              help="몇 가지 질문에 답하면 메뉴 조합을 추천해 드려요")
    for c in ctx.CATEGORIES:
        if st.button(f"{c['icon']}  {c['name']}", key=f"cat_{c['id']}", width="stretch",
                     type="primary" if st.session_state.cat == c["id"] else "secondary"):
            st.session_state.cat = c["id"]
            st.rerun()


def render_menu():
    cat = st.session_state.cat
    if cat == "ai":
        render_recommendations()
        return
    items = [m for m in ctx.MENU if "BEST" in m["tags"]] if cat == "best" else [m for m in ctx.MENU if m["cat"] == cat]
    category = ctx.CATEGORY_BY_ID[cat]
    st.html(f'<div class="section-title">{category["icon"]} {category["name"]} <span>{len(items)}</span></div>')
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
