"""관리자 페이지: streamlit run admin/app.py --server.port 8502"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from shared.api import get

st.set_page_config(page_title="Table Order 관리자", page_icon="🛠️")
st.title("주문 관리")
token = st.sidebar.text_input("관리자 토큰", type="password")
if token:
    try:
        st.write(get("/admin/api/orders", token))
    except Exception as e:
        st.error(f"불러오지 못했습니다: {e}")
