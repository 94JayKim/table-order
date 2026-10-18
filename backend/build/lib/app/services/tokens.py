"""로그인 후 발급하는 JWT."""

from datetime import datetime, timedelta, timezone

import jwt


def issue(member_id: int, secret: str, expire_minutes: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    return jwt.encode({"sub": str(member_id), "exp": exp}, secret, algorithm="HS256")


def decode(token: str, secret: str) -> int | None:
    try:
        return int(jwt.decode(token, secret, algorithms=["HS256"])["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
