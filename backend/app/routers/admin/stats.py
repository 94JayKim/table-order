"""관리자: 대시보드 통계."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services import stats as stats_service
from app.services.grades import KST

router = APIRouter()


@router.get("/stats")
async def dashboard(request: Request, settings: Settings = Depends(get_settings)):
    s = request.app.state
    return stats_service.dashboard(s.shop.orders(), s.members.all(), s.shop.recommendation_count(),
                                   datetime.now(KST).date(), grade_rule(settings))
