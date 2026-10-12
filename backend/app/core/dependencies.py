"""관리자 인증 등 공통 의존성."""

from fastapi import Depends, Header, HTTPException

from app.core.settings import Settings, get_settings


def require_admin(
    authorization: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if authorization != f"Bearer {settings.admin_token}":
        raise HTTPException(status_code=401, detail="관리자 인증이 필요합니다.")
