"""관리자 인증 등 공통 의존성."""

from fastapi import Depends, Header, HTTPException, Request

from app.core.settings import Settings, get_settings
from app.services import tokens


def require_admin(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if authorization != f"Bearer {settings.admin_token}":
        raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")


def current_member(request: Request, authorization: str = Header(default=""),
                   settings: Settings = Depends(get_settings)) -> dict:
    """로그인한 손님. 'Authorization: Bearer <JWT>' 를 검증한다."""
    member_id = tokens.decode(authorization.removeprefix("Bearer ").strip(), settings.jwt_secret)
    member = request.app.state.members.get(member_id) if member_id else None
    if not member:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return member


def optional_member(request: Request, authorization: str = Header(default=""),
                    settings: Settings = Depends(get_settings)) -> dict | None:
    """로그인 여부와 상관없이 쓰는 API(주문 등)에서 회원이면 회원 정보를 붙인다. 잘못된 토큰은 비회원으로 본다."""
    member_id = tokens.decode(authorization.removeprefix("Bearer ").strip(), settings.jwt_secret)
    return request.app.state.members.get(member_id) if member_id else None
