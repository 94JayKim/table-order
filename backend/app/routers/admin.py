"""관리자 페이지용 API. 모든 경로에 관리자 인증이 필요하다."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field

from app.core.dependencies import require_admin
from app.core.settings import Settings, get_settings
from app.services import stats
from app.services.grades import GRADES, KST, age_group, gender_label, grade_of
from app.services.sens import SmsRejected, SmsService
from datetime import datetime

router = APIRouter(prefix="/admin/api", tags=["관리자"], dependencies=[Depends(require_admin)])

CATEGORIES = [{"id": "chicken", "name": "치킨·튀김"}, {"id": "anju", "name": "안주"}, {"id": "soup", "name": "탕·전골"},
              {"id": "beer", "name": "맥주"}, {"id": "soju", "name": "소주·막걸리"}, {"id": "side", "name": "음료·사이드"}]
CAT_IDS = {c["id"] for c in CATEGORIES}


class MenuIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    cat: str | None = None
    price: int | None = Field(default=None, ge=0)
    desc: str | None = None
    image_url: str | None = None
    soldout: bool | None = None
    spicy: int | None = Field(default=None, ge=0, le=3)
    weight: int | None = Field(default=None, ge=0, le=100)  # OWNER 추천 가중치
    set_ok: bool | None = None
    emoji: str | None = None
    tags: list[str] | None = None


class SmsIn(BaseModel):
    grades: list[str] = Field(min_length=1)
    body: str


def _rule(s: Settings, repeat=None, regular=None, dormant=None) -> dict:
    return {"repeat": repeat or s.grade_repeat_visits, "regular": regular or s.grade_regular_visits,
            "dormant": dormant or s.grade_dormant_days}


def _sms(request: Request) -> SmsService:
    return request.app.state.sms


@router.get("/menus")
async def menus(request: Request):
    return {"categories": CATEGORIES, "menus": request.app.state.shop.menus()}


@router.put("/menus/{menu_id}")
async def save_menu(menu_id: str, body: MenuIn, request: Request):
    """없는 id 면 새 메뉴를 만든다(이름·카테고리·가격 필수), 있으면 보낸 필드만 수정한다."""
    shop = request.app.state.shop
    fields = body.model_dump(exclude_none=True)
    if "cat" in fields and fields["cat"] not in CAT_IDS:
        raise HTTPException(422, "알 수 없는 카테고리입니다.")
    if not shop.menu(menu_id) and not {"name", "cat", "price"} <= fields.keys():
        raise HTTPException(422, "새 메뉴는 name, cat, price 가 필요합니다.")
    return shop.save_menu(menu_id, fields)


@router.delete("/menus/{menu_id}", status_code=204)
async def delete_menu(menu_id: str, request: Request):
    if not request.app.state.shop.delete_menu(menu_id):
        raise HTTPException(404, "없는 메뉴입니다.")


@router.get("/orders")
async def list_orders(request: Request, member_id: int | None = None):
    members = {m["id"]: m for m in request.app.state.members.all()}
    out = []
    for o in request.app.state.shop.orders(member_id):
        m = members.get(o["member_id"])
        out.append({**o, "nickname": m["nickname"] if m else None})
    return out


@router.get("/calls")
async def list_calls(request: Request):
    return request.app.state.shop.calls()


@router.post("/calls/{call_id}/done")
async def finish_call(call_id: int, request: Request):
    call = request.app.state.shop.finish_call(call_id)
    if not call:
        raise HTTPException(404, "없는 호출입니다.")
    return call


@router.get("/members")
async def list_members(request: Request, settings: Settings = Depends(get_settings),
                       repeat: int | None = Query(default=None, ge=2), regular: int | None = Query(default=None, ge=3),
                       dormant: int | None = Query(default=None, ge=1)):
    """고객 목록과 등급. 등급 기준은 쿼리로 미리 바꿔 볼 수 있다 (저장되지는 않음)."""
    rule, today = _rule(settings, repeat, regular, dormant), datetime.now(KST).date()
    return {"rule": rule, "members": [
        {"id": m["id"], "nickname": m["nickname"], "gender": gender_label(m["gender"]),
         "age_group": age_group(m["birth_year"], today), "visit_count": m["visit_count"],
         "last_visit_at": m["last_visit_at"], "marketing_consent": bool(m["marketing_consent"]),
         "opted_out": bool(m["opted_out"]), "has_phone": bool(m["phone"]), "grade": grade_of(m, today, **rule)}
        for m in request.app.state.members.all()]}


@router.post("/members/{member_id}/opt-out")
async def member_opt_out(member_id: int, request: Request):
    if not request.app.state.members.opt_out(member_id):
        raise HTTPException(404, "없는 회원입니다.")
    return {"ok": True}


@router.get("/stats")
async def dashboard(request: Request, settings: Settings = Depends(get_settings)):
    s = request.app.state
    return stats.dashboard(s.shop.orders(), s.members.all(), s.shop.recommendation_count(),
                           datetime.now(KST).date(), _rule(settings))


@router.get("/marketing/sms/usage")
async def sms_usage(request: Request):
    return _sms(request).usage()


@router.post("/marketing/sms/preview")
async def sms_preview(body: SmsIn, request: Request):
    _check_grades(body.grades)
    return _sms(request).preview(body.grades, body.body)


@router.post("/marketing/sms/send")
def sms_send(body: SmsIn, request: Request):
    _check_grades(body.grades)
    try:
        return _sms(request).send(body.grades, body.body)
    except SmsRejected as e:
        raise HTTPException(409, {"problems": e.problems})


@router.get("/marketing/sms/logs")
async def sms_logs(request: Request):
    return request.app.state.sms_logs.logs()


def _check_grades(grades: list[str]) -> None:
    if any(g not in GRADES for g in grades):
        raise HTTPException(422, f"등급은 {GRADES} 중에서 고르세요.")
