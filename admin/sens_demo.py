"""네이버 클라우드 SENS 문자 발송 더미 (실제 API 호출 없음).

정식 구현에서는 plan() 의 검사들이 서버의 발송 서비스로 옮겨지고,
send 부분만 SENS v2 API 호출로 바뀐다. 한도·규칙 값은 SENS 콘솔과 법규 확인 후 조정할 것.
"""
from datetime import time

SMS_LIMIT_BYTES = 90          # 초과하면 LMS
FREE_SMS, FREE_LMS = 50, 10   # 월 무료 건수 (가정값)
NIGHT_START, NIGHT_END = time(21, 0), time(8, 0)  # 광고성 문자 야간 발송 제한
OPT_OUT = "무료수신거부 080-000-0000"  # 더미 번호


def msg_bytes(text: str) -> int:
    """EUC-KR 기준: 한글 등 2바이트, 영문·숫자·공백 1바이트."""
    return sum(1 if ord(ch) < 128 else 2 for ch in text)


def build_message(body: str, store: str) -> str:
    return f"(광고){store}\n{body.strip()}\n{OPT_OUT}"


def msg_type(text: str) -> str:
    return "SMS" if msg_bytes(text) <= SMS_LIMIT_BYTES else "LMS"


def is_night(now: time) -> bool:
    return now >= NIGHT_START or now < NIGHT_END


def plan(targets: int, text: str, now: time, used: dict) -> dict:
    """발송 가능 여부를 판단한다. used = {"SMS": n, "LMS": n} (이번 달 발송 건수)."""
    kind = msg_type(text)
    limit = FREE_SMS if kind == "SMS" else FREE_LMS
    left = limit - used.get(kind, 0)
    problems = []
    if targets == 0:
        problems.append("발송 대상이 없습니다.")
    if is_night(now):
        problems.append("야간(21시~08시)에는 광고성 문자를 보낼 수 없습니다.")
    if targets > left:
        problems.append(f"이번 달 {kind} 무료 잔여 {max(left, 0)}건보다 대상({targets}명)이 많습니다.")
    return {"type": kind, "bytes": msg_bytes(text), "left": left, "ok": not problems, "problems": problems}
