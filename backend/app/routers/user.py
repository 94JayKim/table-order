"""사용자(손님) 페이지용 API."""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["사용자"])


@router.get("/menus")
async def list_menus():
    return []
