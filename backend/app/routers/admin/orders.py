"""관리자: 주문 이력, 직원 호출."""

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


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
