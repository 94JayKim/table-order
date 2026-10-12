"""사용자(손님) 페이지: streamlit run user/app.py --server.port 8501"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from shared.api import get

st.set_page_config(page_title="Table Order", page_icon="🍺")
st.title("메뉴")
try:
    st.write(get("/api/menus"))
except Exception as e:
    st.error(f"서버에 연결할 수 없습니다: {e}")
