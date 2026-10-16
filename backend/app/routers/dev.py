"""개발 환경에서만 사용하는 DB 연결 확인 API."""

from fastapi import APIRouter, HTTPException, Request

from app.stores.dev_test import DevTestStore

router = APIRouter(prefix="/api", tags=["개발"])


@router.post("/dev/db-test")
async def db_test(request: Request):
    """test 테이블에 값을 쓰고 다시 읽어 DB 왕복 여부를 확인한다."""
    if not request.app.state.settings.dev_test_button:
        raise HTTPException(status_code=404, detail="개발용 테스트 기능이 꺼져 있습니다.")
    return DevTestStore(request.app.state.db).round_trip()
