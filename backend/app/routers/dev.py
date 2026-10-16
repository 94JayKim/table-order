"""개발 전용 API. 운영 환경에서는 설정으로 경로를 닫는다."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.settings import get_settings

router = APIRouter(prefix="/api/dev", tags=["개발"])


@router.post("/db-test")
async def db_test(request: Request, settings=Depends(get_settings)):
    """test 테이블에 쓰고 읽은 값이 같은지 반환한다."""
    if not settings.dev_test_button:
        raise HTTPException(status_code=404, detail="Not Found")
    return {"result": 1 if request.app.state.dev_test.insert_and_check() else 0}
