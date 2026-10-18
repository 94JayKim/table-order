"""관리자: 메뉴 관리."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter()


def menu_categories(request: Request) -> list[dict]:
    """메뉴를 넣을 수 있는 카테고리를 저장소에서 가져온다."""
    return request.app.state.shop.menu_categories()


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


@router.get("/menus")
async def menus(request: Request):
    """관리자 화면에 필요한 카테고리와 메뉴 목록을 돌려준다."""
    return {"categories": menu_categories(request), "menus": request.app.state.shop.menus()}


@router.put("/menus/{menu_id}")
async def save_menu(menu_id: str, body: MenuIn, request: Request):
    """새 메뉴는 필수값을 확인하고, 기존 메뉴는 받은 값만 저장한다."""
    shop = request.app.state.shop
    # 부분 수정에서는 생략한 필드를 유지하고, 명시적인 null도 저장하지 않는다.
    fields = body.model_dump(exclude_unset=True, exclude_none=True)
    existing = shop.menu(menu_id)

    # 새 메뉴 등록 때만 필수값을 검사해 부분 수정 요청을 막지 않는다.
    if existing is None:
        required = ("name", "cat", "price")
        missing = [field for field in required if field not in fields]
        if missing:
            labels = {"name": "메뉴 이름", "cat": "카테고리", "price": "가격"}
            missing_labels = ", ".join(labels[field] for field in missing)
            raise HTTPException(422, f"새 메뉴 등록에 필요한 항목을 입력해 주세요: {missing_labels}.")

    # 카테고리는 새 메뉴 등록과 카테고리 변경 때 실제 메뉴 카테고리인지 확인한다.
    if "cat" in fields and fields["cat"] not in {category["id"] for category in menu_categories(request)}:
        raise HTTPException(422, "존재하지 않는 메뉴 카테고리입니다.")

    return shop.save_menu(menu_id, fields)


@router.delete("/menus/{menu_id}", status_code=204)
async def delete_menu(menu_id: str, request: Request):
    """메뉴를 삭제하고, 없는 메뉴면 404를 돌려준다."""
    if not request.app.state.shop.delete_menu(menu_id):
        raise HTTPException(404, "메뉴를 찾을 수 없습니다.")
    return None
