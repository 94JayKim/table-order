"""QR 로그인 더미 흐름 (카카오·서버·WebSocket 없이 상태 전이만 흉내).

정식 구현에서는 이 상태가 FastAPI 서버의 로그인 세션이 되고,
스캔/승인은 휴대폰의 카카오 로그인 콜백이 일으킨다.
"""
import uuid

TTL_SECONDS = 180


def new_session(now: float) -> dict:
    return {"token": uuid.uuid4().hex[:12], "created": now, "status": "waiting", "member": None}


def state(s: dict, now: float) -> str:
    """waiting → scanned → logged_in, 또는 expired. 로그인 완료 후에는 만료되지 않는다."""
    if s["status"] == "logged_in":
        return "logged_in"
    if now - s["created"] > TTL_SECONDS:
        return "expired"
    return s["status"]


def scan(s: dict, now: float) -> bool:
    if state(s, now) != "waiting":
        return False
    s["status"] = "scanned"
    return True


def approve(s: dict, now: float, member: dict) -> bool:
    """일회용: 스캔된 세션만 한 번 승인할 수 있다."""
    if state(s, now) != "scanned":
        return False
    s["status"] = "logged_in"
    s["member"] = member
    return True


def remaining(s: dict, now: float) -> int:
    return max(0, int(TTL_SECONDS - (now - s["created"])))
