"""DB에서 읽은 주문·회원으로 대시보드 기본 통계를 계산한다."""

from collections import Counter
from datetime import date, datetime, timezone

from app.services.grades import AGE_GROUPS, KST, age_group, gender_label, grade_of


def order_date(value: str) -> date:
    """시간대 없는 SQLite 시각도 UTC로 해석해 한국 날짜를 구한다."""
    timestamp = datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(KST).date()


def dashboard(orders: list[dict], members: list[dict], recommendations: int, today: date, rule: dict) -> dict:
    """오늘 지표와 전체 기록 지표를 기존 화면의 응답 모양으로 돌려준다."""
    todays = [order for order in orders if order_date(order["ts"]) == today]
    # 같은 회원이 여러 번 주문해도 고객 수는 한 명으로 센다. 비회원은 분류하지 않는다.
    customer_ids = {order["member_id"] for order in todays if order.get("member_id") is not None}
    grades = Counter(grade_of(member, today, **rule) for member in members if member["id"] in customer_ids)
    ages = Counter(age_group(member.get("birth_year"), today) for member in members)
    genders = Counter(gender_label(member.get("gender")) for member in members)
    popularity = Counter()
    for order in orders:
        for line in order.get("lines", []):
            # 조합 두 세트에 메뉴가 두 개씩 있으면 해당 메뉴 수량은 네 개다.
            if line.get("kind") == "combo" or str(line.get("id", "")).startswith("combo:"):
                for component in line.get("components", []):
                    popularity[component["name"]] += component["qty"] * line["qty"]
            else:
                popularity[line["name"]] += line["qty"]
    ai_orders = sum(bool(order.get("ai_combo")) for order in orders)
    return {
        "today_orders": len(todays),
        "avg_order_amount": sum(order["total"] for order in todays) // len(todays) if todays else 0,
        "new_customers": grades["신규"],
        "returning_customers": grades["재방문"] + grades["단골"],
        "age_groups": {group: ages[group] for group in AGE_GROUPS},
        "genders": {gender: genders[gender] for gender in ("여", "남") if genders[gender]},
        "popular_menus": [{"name": name, "qty": qty} for name, qty in
                          sorted(popularity.items(), key=lambda item: (-item[1], item[0]))[:10]],
        "ai": {"recommendations": recommendations, "ai_orders": ai_orders,
               "hit_rate": ai_orders / recommendations if recommendations else None,
               "definition": "전체 AI 조합이 포함된 주문 수 / 전체 추천 노출 횟수 (임시 기준)"},
    }
