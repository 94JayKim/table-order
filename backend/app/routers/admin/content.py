"""관리자: 화면용 콘텐츠(카테고리·룰렛·직원 호출 항목 등) 교체."""

from fastapi import APIRouter, Body, HTTPException, Request

router = APIRouter()


@router.put("/content/{name}")
async def save_content(name: str, request: Request, data: dict | list = Body(...)):
    """콘텐츠를 통째로 교체한다. 기존과 같은 종류(목록/객체)이고 비어 있지 않아야 한다."""
    store = request.app.state.content
    current = store.get(name)
    if current is None:
        raise HTTPException(404, "없는 콘텐츠입니다.")
    if type(data) is not type(current) or not data:
        raise HTTPException(422, f"{name} 는 비어 있지 않은 {'목록' if isinstance(current, list) else '객체'} 여야 합니다.")
    if name == "roulette_prizes":
        _check_roulette(data)
    store.set(name, data)
    return data


def _check_roulette(prizes: list) -> None:
    """룰렛 칸: 2~8개, 종류(할인/서비스)별 필수값, 확률 가중치(weight)는 0 이상이고 합이 0보다 커야 한다."""
    if not 2 <= len(prizes) <= 8:
        raise HTTPException(422, "룰렛 칸은 2~8개여야 합니다.")
    for p in prizes:
        if not isinstance(p, dict) or p.get("kind") not in ("discount", "free") or not p.get("label") or not p.get("short"):
            raise HTTPException(422, "룰렛 칸에는 label, short, kind(discount|free) 가 필요합니다.")
        if p["kind"] == "discount" and not (isinstance(p.get("percent"), int) and 1 <= p["percent"] <= 100):
            raise HTTPException(422, "할인 칸의 percent 는 1~100 이어야 합니다.")
        if p["kind"] == "free" and not p.get("item_id"):
            raise HTTPException(422, "서비스 칸에는 item_id 가 필요합니다.")
        if not isinstance(p.get("weight", 1), (int, float)) or p.get("weight", 1) < 0:
            raise HTTPException(422, "weight 는 0 이상의 숫자여야 합니다.")
    if not any(p.get("weight", 1) > 0 for p in prizes):
        raise HTTPException(422, "weight 가 0보다 큰 칸이 하나는 있어야 합니다.")
