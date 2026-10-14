"""추천 가중치 화면.
"""

from html import escape

import streamlit as st

from admin.ui.widgets import page_head, sec_title

ss = st.session_state


WEIGHT_STEP = 5


def weight_change(key, delta):
    ss[key] = min(100, max(0, ss[key] + delta))


def weight_thumb(menu_row, visual):
    """주문 화면처럼 메뉴 사진(없으면 이모지+카테고리 색)을 보여주는 썸네일."""
    c1, c2 = visual["colors"]
    sold = "" if menu_row["판매 여부"] else '<div class="soldout">품절</div>'
    if visual["image_url"]:
        inner = f'<img src="{escape(visual["image_url"], quote=True)}" alt="{escape(menu_row["메뉴명"], quote=True)}" loading="lazy">'
    else:
        inner = visual["emoji"]
    return f'<div class="wthumb" style="background:linear-gradient(135deg,{c1},{c2})">{inner}{sold}</div>'


def page_weights(repo):
    page_head("추천 가중치", "메뉴 사진 아래 + / − 로 조절하세요. 0~100, 높을수록 AI 추천 조합에 우선 반영돼요 (기본 50).")
    menu = repo.menus()
    visuals = repo.menu_visuals()
    cat = st.selectbox("카테고리", ["전체"] + [c["name"] for c in repo.categories()])
    view = menu if cat == "전체" else menu[menu["카테고리"] == cat]
    # 가중치 상태: 다른 화면(메뉴 관리 등)에서 저장값이 바뀌었으면 그 값으로 다시 시작한다
    for _, row in menu.iterrows():
        key, base = f"w_{row['id']}", f"wbase_{row['id']}"
        if key not in ss or ss.get(base) != int(row["추천 가중치"]):
            ss[key], ss[base] = int(row["추천 가중치"]), int(row["추천 가중치"])
    new = menu.copy()
    for idx, row in menu.iterrows():
        new.at[idx, "추천 가중치"] = ss[f"w_{row['id']}"]
    dirty = not new["추천 가중치"].equals(menu["추천 가중치"])

    with st.container(horizontal=True, key="wgrid"):
        for _, row in view.iterrows():
            key, saved = f"w_{row['id']}", int(row["추천 가중치"])
            with st.container(key=f"wcard_{row['id']}"):
                st.html(weight_thumb(row, visuals.get(row["id"], {"emoji": "🍽️", "image_url": "", "colors": ["#a29bfe", "#6c5ce7"]}))
                        + f'<div class="wname">{escape(row["메뉴명"])}</div>'
                        f'<div class="wprice">{row["가격"]:,}원</div>')
                c1, c2, c3 = st.columns([1, 1.3, 1], vertical_alignment="center", wrap=False)
                c1.button("−", key=f"wdec_{row['id']}", width="stretch", on_click=weight_change, args=(key, -WEIGHT_STEP),
                          disabled=ss[key] <= 0, help=f"{row['메뉴명']} 가중치 낮추기")
                changed = " changed" if ss[key] != saved else ""
                c2.html(f'<div class="wval{changed}"><b>{ss[key]}</b><small>저장값 {saved}</small></div>')
                c3.button("+", key=f"winc_{row['id']}", width="stretch", on_click=weight_change, args=(key, WEIGHT_STEP),
                          disabled=ss[key] >= 100, help=f"{row['메뉴명']} 가중치 높이기")

    def undo_weights():
        for key in [k for k in ss if str(k).startswith(("w_", "wbase_"))]:
            del ss[key]  # 저장된 값으로 다시 시작한다
        st.toast("저장하지 않은 변경을 되돌렸어요.", icon="↩️")

    sec_title("변경 사항", f"{int((new['추천 가중치'] != menu['추천 가중치']).sum())}개 메뉴 수정됨")
    c_save, c_undo, _ = st.columns([1.2, 1.3, 5])
    c_undo.button("↩ 되돌리기", key="weights_undo", width="stretch", disabled=not dirty, on_click=undo_weights,
                  help="저장하기 전의 가중치 변경을 모두 취소하고 저장된 값으로 돌립니다")
    if c_save.button("가중치 저장", type="primary", width="stretch"):
        r = repo.save_menus(new, menu)
        st.toast(f"저장했습니다. (수정 {r['saved']}개)", icon="✅")
        st.rerun()  # 저장된 값을 기준으로 다시 그린다 (되돌리기 버튼 상태 갱신)
