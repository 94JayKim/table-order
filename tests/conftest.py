import pytest
import streamlit as st


@pytest.fixture(autouse=True)
def fresh_streamlit_cache():
    """서버 데이터는 10초 캐시되므로(운영에서는 의도된 동작) 테스트마다 비운다."""
    st.cache_data.clear()
    yield
    st.cache_data.clear()
