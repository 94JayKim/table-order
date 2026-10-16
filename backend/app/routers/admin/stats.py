"""관리자: 대시보드 통계."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.settings import Settings, get_settings
from app.routers.admin.common import grade_rule
from app.services import stats as stats_service
from app.services.grades import KST
from app.stores.stats import StatsStore

router = APIRouter()


def dashboard(request: Request, settings: Settings = Depends(get_settings),
              repeat: int | None = Query(default=None, ge=2),
              regular: int | None = Query(default=None, ge=3),
              dormant: int | None = Query(default=None, ge=1)) -> dict:
    """조회 기준만 바꿔 계산하며 회원 기록이나 서버 설정은 저장하지 않는다."""
    rule = grade_rule(settings, repeat, regular, dormant)
    if rule["regular"] <= rule["repeat"]:
        raise HTTPException(422, "단골 기준은 재방문 기준보다 커야 합니다.")
    store = StatsStore(request.app.state.db)
    return stats_service.dashboard(store.orders(), request.app.state.members.all(),
                                   store.recommendation_count(), datetime.now(KST).date(), rule)


# 각 세부 API는 같은 의존 함수로 집계해 계산 규칙이 서로 달라지지 않게 한다.
@router.get("/stats")
def all_stats(result: dict = Depends(dashboard)):
    return result


@router.get("/stats/sales")
def sales(result: dict = Depends(dashboard)):
    return {key: result[key] for key in ("today_orders", "avg_order_amount")}


@router.get("/stats/menus/ranking")
def menu_ranking(result: dict = Depends(dashboard)):
    return {"popular_menus": result["popular_menus"]}


@router.get("/stats/customers")
def customers(result: dict = Depends(dashboard)):
    return {key: result[key] for key in ("new_customers", "returning_customers", "age_groups", "genders")}


@router.get("/stats/ai-recommendations")
def ai_recommendations(result: dict = Depends(dashboard)):
    return result["ai"]
