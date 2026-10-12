"""user 페이지의 서버 연동 계층 (QR 로그인·회원 정보). 서버가 없으면 None 을 돌려주고 해당 기능만 꺼진다."""
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from shared import api

RETRY_AFTER = 15  # 서버가 안 닿으면 이 시간(초) 동안은 다시 시도하지 않는다 (화면이 매번 멈추지 않게)


def is_online() -> bool:
    return st.session_state.get("offline_until", 0) <= time.time()


def _mark_offline() -> None:
    st.session_state["offline_until"] = time.time() + RETRY_AFTER


def _call(fn, *args, **kw):
    if not is_online():
        return None
    try:
        return fn(*args, **kw)
    except api.ApiUnavailable:
        _mark_offline()
    except api.ApiError:
        pass
    return None


def create_qr(table_no: int):
    """{token, secret, qr_url, expires_in} 또는 None."""
    return _call(api.post, "/api/auth/qr", None, json={"table_no": table_no})


def poll_login(secret: str):
    """{event:'status', status, remaining} / {event:'logged_in', member, access_token} 또는 None."""
    return _call(api.get, f"/api/auth/qr/{secret}")


def update_profile(token: str, **fields):
    """(성공 여부, 메시지)."""
    try:
        api.patch("/api/members/me", token, json={k: v for k, v in fields.items() if v is not None})
        return True, "저장했어요."
    except api.ApiError as e:
        return False, "입력한 내용을 확인해 주세요." if e.status == 422 else "저장하지 못했어요."
    except api.ApiUnavailable:
        _mark_offline()
        return False, "서버에 연결할 수 없어요."


def opt_out(token: str) -> bool:
    return _call(api.post, "/api/members/me/opt-out", token) is not None
