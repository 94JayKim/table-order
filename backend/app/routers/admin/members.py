"""관리자: 고객 목록·등급·수신거부."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services.grades import KST, age_group, gender_label, grade_counts, grade_of

router = APIRouter()


@router.get("/members")
async def list_members(request: Request, settings: Settings = Depends(get_settings),
                       repeat: int | None = Query(default=None, ge=2), regular: int | None = Query(default=None, ge=3),
                       dormant: int | None = Query(default=None, ge=1)):
    """고객 목록과 등급. 등급 기준은 쿼리로 미리 바꿔 볼 수 있다 (저장되지는 않음)."""
    rule, today = grade_rule(settings, repeat, regular, dormant), datetime.now(KST).date()
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


@router.get("/customers/grades")
async def customer_grades(request: Request, settings: Settings = Depends(get_settings),
                          repeat: int | None = Query(default=None, ge=2),
                          regular: int | None = Query(default=None, ge=3),
                          dormant: int | None = Query(default=None, ge=1)):
    """회원의 방문 기록을 읽어 요청한 기준으로 등급별 인원을 반환한다."""
    # 쿼리는 이번 조회에만 적용하고, 없는 값은 서버 설정을 사용한다.
    rule = grade_rule(settings, repeat, regular, dormant)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    return grade_counts(request.app.state.members.all(), datetime.now(KST).date(), **rule)


@router.get("/customers/grades/rules")
async def customer_grade_rules(settings: Settings = Depends(get_settings)):
    """화면의 초기값·기본값 복원에 쓰는 현재 서버 등급 기준을 반환한다."""
    return grade_rule(settings)


# 새 고객 경로에서도 기존 함수를 그대로 사용해 목록·수신거부 응답 계약을 유지한다.
router.add_api_route("/customers", list_members, methods=["GET"])
router.add_api_route("/customers/{member_id}/opt-out", member_opt_out, methods=["POST"])


@router.get("/marketing/regular-preferences")
async def regular_preferences(request: Request, settings: Settings = Depends(get_settings)):
    """오늘 주문한 단골의 방문 기록과 확인 가능한 메뉴 선호도를 조회한다."""
    from app.services.customer_notes import regular_notes
    from app.stores.customer_notes import CustomerNotesStore

    # 기존 고객 목록 응답은 유지하고 마케팅 화면에서만 선호도 조회를 사용한다.
    store = CustomerNotesStore(request.app.state.db)
    notes = regular_notes(request.app.state.members.all(), store.orders(), store.lines(), store.menus(),
                          datetime.now(KST).date(), dormant_days=settings.grade_dormant_days,
                          regular_visits=settings.grade_regular_visits)
    return {"preferences": notes}
