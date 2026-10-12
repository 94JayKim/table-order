"""취향과 주문 정보를 반영하는 데모 조합 추천 및 세트 가격 계산."""
from collections import Counter

from menu_data import MENU_BY_ID


DISCOUNT_PERCENT = 10
PAIRINGS = [
    ("classic", "바삭한 치킨 한 상", ("c1", "c6"), "바삭한 통닭에 고소한 치즈 감자튀김을 곁들여 함께 나눠 먹기 좋아요."),
    ("garlic", "달콤짭짤 마늘치킨", ("c2", "c7"), "달콤짭짤한 마늘치킨과 부드러운 크림치즈볼로 맛과 식감을 다르게 즐길 수 있어요."),
    ("light", "가볍게 즐기는 먹태", ("a1", "a4"), "담백하고 쫄깃한 먹태에 부드러운 계란말이를 더해 식감을 균형 있게 구성했어요."),
    ("spicy", "매콤한 골뱅이 한 상", ("a2", "a4"), "새콤매콤한 골뱅이 소면에 부드러운 계란말이를 곁들여 매운맛을 쉬어 갈 수 있어요."),
    ("fire", "불향 가득 닭발 조합", ("a3", "d5"), "불향 나는 매콤한 닭발에 고소한 주먹밥을 더해 든든하게 즐길 수 있어요."),
    ("soup", "뜨끈한 국물 한 상", ("s2", "a8"), "시원한 어묵탕과 바삭한 해물파전으로 국물과 안주를 함께 즐길 수 있어요."),
    ("seafood", "얼큰한 해물 조합", ("s1", "c4"), "얼큰한 짬뽕탕에 바삭한 오징어 튀김을 곁들여 국물과 튀김의 식감을 살렸어요."),
    ("value", "알뜰하게 나누는 한 상", ("c3", "c7"), "쫄깃한 닭똥집과 고소한 치즈볼로 부담 적은 가격에 두 가지 안주를 즐길 수 있어요."),
    ("comfort", "고소하고 부드러운 조합", ("a4", "c7"), "부드러운 계란말이와 고소한 크림치즈볼로 맵지 않은 안주를 구성했어요."),
    ("dry", "건어물과 소시지 조합", ("a10", "a5"), "오래 나눠 먹기 좋은 건어물에 따뜻한 모둠 소시지를 곁들였어요."),
]
DRINKS = {"맥주": "b1", "소주": "j1", "음료": "d2", "없이": None}


def ordered_counts(lines):
    counts = Counter()
    for line in lines:
        if "components" in line:
            for component in line["components"]:
                counts[component["id"]] += component["qty"] * line["qty"]
        else:
            counts[line["id"]] += line["qty"]
    return counts


def recommend_combos(people=2, budget=40000, spicy="상관없어요", drink="맥주", lines=()):
    """예산/품절/맵기 조건을 지킨 후보를 점수순으로 최대 세 개 반환."""
    counts = ordered_counts(lines)
    preferred_categories = Counter()
    for item_id, count in counts.items():
        if item_id in MENU_BY_ID:
            preferred_categories[MENU_BY_ID[item_id]["cat"]] += count
    portions = 2 if people >= 4 else 1
    recommendations = []
    for combo_id, title, ids, pairing_reason in PAIRINGS:
        if spicy == "매콤하게":
            ids = tuple(f"{item_id}-hot" if item_id in ("a2", "a3") else item_id for item_id in ids)
        selected_ids = list(ids)
        if DRINKS[drink]:
            selected_ids.append(DRINKS[drink])
        if any(MENU_BY_ID[item_id]["soldout"] for item_id in selected_ids):
            continue
        spicy_items = [MENU_BY_ID[item_id] for item_id in ids
                       if "매운맛" in MENU_BY_ID[item_id]["tags"]]
        if spicy == "맵지 않게" and spicy_items:
            continue
        components = []
        for item_id in selected_ids:
            item = MENU_BY_ID[item_id]
            qty = people if item_id == DRINKS[drink] else portions
            components.append({"id": item_id, "name": item["name"], "emoji": item["emoji"],
                               "qty": qty, "opt": "", "unit": item["price"]})
        original = sum(c["unit"] * c["qty"] for c in components)
        discount = original * DISCOUNT_PERCENT // 100
        price = original - discount
        if price > budget:
            continue
        popular = sum("BEST" in MENU_BY_ID[item_id]["tags"] for item_id in ids)
        overlap = sum(counts[item_id] > 0 for item_id in ids)
        affinity = sum(min(preferred_categories[MENU_BY_ID[item_id]["cat"]], 3) for item_id in ids)
        score = popular * 4 + affinity * 2 - overlap * 15
        if spicy == "매콤하게":
            score += 20 if spicy_items else -10
        score += 3 * (1 - abs(price - budget * .8) / budget)
        reason = f"{people}명이 나눠 먹도록 안주 수량을 맞췄어요. " + pairing_reason
        if spicy == "맵지 않게":
            reason += " 매운맛 메뉴는 제외했어요."
        elif spicy == "매콤하게" and spicy_items:
            reason += " 선택한 매콤한 취향을 반영했어요."
        if drink != "없이":
            reason += f" {drink}도 1인당 1개씩 포함했어요."
        if counts:
            reason += " " + ("기존 주문과 겹치는 안주가 포함되어 있어요." if overlap else "장바구니·주문 내역의 안주와 겹치지 않게 골랐어요.")
        recommendations.append({"id": combo_id, "name": title, "components": components,
                                "original": original, "discount": discount, "price": price,
                                "reason": reason, "score": score})
    recommendations.sort(key=lambda combo: (-combo["score"], combo["price"], combo["id"]))
    return recommendations[:3]


def combo_cart_line(combo):
    """구성/가격별 세트 행을 만들어 할인 금액을 주문까지 유지."""
    signature = ";".join(f"{c['id']}:{c['qty']}:{c['opt']}" for c in combo["components"])
    key = f"combo:{combo['id']}|{signature}|{combo['price']}"
    description = " + ".join(f"{c['name']} × {c['qty']}" + (f" ({c['opt']})" if c["opt"] else "")
                             for c in combo["components"])
    line = {"id": f"combo:{combo['id']}", "name": f"[AI 조합] {combo['name']}",
            "opt": description, "unit": combo["price"], "original_unit": combo["original"],
            "qty": 1, "components": [dict(c) for c in combo["components"]]}
    return key, line
