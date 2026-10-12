"""관리자 페이지용 API. 모든 경로에 관리자 인증이 필요하다."""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_admin

router = APIRouter(
    prefix="/admin/api", tags=["관리자"], dependencies=[Depends(require_admin)]
)


@router.get("/orders")
async def list_orders():
    return []
