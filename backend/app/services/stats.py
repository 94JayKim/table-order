"""관리자 대시보드 통계."""

from collections import Counter
from datetime import date

from app.services.grades import AGE_GROUPS, age_group, gender_label, grade_of, to_kst_date


def _menu_counts(orders: list[dict]) -> Counter:
    counts: Counter = Counter()
    for o in orders:
        for line in o["lines"]:
            if line.get("components"):  # AI 조합은 구성 메뉴 단위로 센다
                for c in line["components"]:
                    counts[c["name"]] += c["qty"] * line["qty"]
            else:
                counts[line["name"]] += line["qty"]
    return counts


def dashboard(orders: list[dict], members: list[dict], recommendations: int, today: date, rule: dict) -> dict:
    by_id = {m["id"]: m for m in members}
    todays = [o for o in orders if to_kst_date(o["ts"]) == today]
    buyers = {by_id[o["member_id"]] ["id"]: by_id[o["member_id"]] for o in todays if o["member_id"] in by_id}
    grades = {mid: grade_of(m, today, **rule) for mid, m in buyers.items()}
    ages = Counter(a for m in members if (a := age_group(m["birth_year"], today)))
    genders = Counter(g for m in members if (g := gender_label(m["gender"])))
    ai_orders = sum(1 for o in orders if o["ai_combo"])
    return {
        "today_orders": len(todays),
        "avg_order_amount": int(sum(o["total"] for o in todays) / len(todays)) if todays else 0,
        "new_customers": sum(1 for g in grades.values() if g == "신규"),
        "returning_customers": sum(1 for g in grades.values() if g in ("재방문", "단골")),
        "age_groups": {k: ages.get(k, 0) for k in AGE_GROUPS},
        "genders": dict(genders),
        "popular_menus": [{"name": n, "qty": q} for n, q in _menu_counts(orders).most_common(10)],
        "ai": {"recommendations": recommendations, "ai_orders": ai_orders,
               "hit_rate": round(ai_orders / recommendations, 3) if recommendations else None,
               "definition": "AI 조합이 포함된 주문 수 / 추천이 노출된 횟수 (임시 기준)"},
    }
