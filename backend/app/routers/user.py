"""사용자(손님) 페이지용 API."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.dependencies import current_member

router = APIRouter(prefix="/api", tags=["사용자"])


@router.get("/menus")
async def list_menus():
    return []


class ProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, pattern=r"^01[016789]-?\d{3,4}-?\d{4}$")
    marketing_consent: bool | None = None


def _me(m: dict) -> dict:
    return {"id": m["id"], "nickname": m["nickname"], "phone": m["phone"],
            "marketing_consent": bool(m["marketing_consent"]), "visit_count": m["visit_count"]}


@router.get("/members/me")
async def get_me(member: dict = Depends(current_member)):
    return _me(member)


@router.patch("/members/me")
async def update_me(body: ProfileUpdate, request: Request, member: dict = Depends(current_member)):
    """휴대폰 번호와 마케팅 수신 동의를 직접 입력받는다 (카카오 번호 수집은 비즈 앱 심사가 필요하므로)."""
    updated = request.app.state.members.update_profile(member["id"], body.phone, body.marketing_consent)
    return _me(updated)
