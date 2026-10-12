"""조합 추천 규칙의 더미 데이터 (JSON 그대로).

API(/api/content 의 rules)와 같은 모양이다. 서버로 바꿔도 recommendations.py 는 그대로 쓴다.
 - pairings: [조합 id, 이름, [메뉴 id...], 추천 문구]
 - drinks: 주종 → 메뉴 id
 - pair_meta: 조합별 음식 종류(kinds)·어울리는 방문 목적(occasions)·분위기(mood)
 - hot_themed: 매운맛을 내세우는 조합 id ("맵지 않게" 선택 시 제외)
"""
RULES = {
    "discount_percent": 10,
    "pairings": [
        ["classic", "바삭한 치킨 한 상", ["c1", "c6"], "바삭한 통닭에 고소한 치즈 감자튀김을 곁들여 함께 나눠 먹기 좋아요."],
        ["garlic", "달콤짭짤 마늘치킨", ["c2", "c7"], "달콤짭짤한 마늘치킨과 부드러운 크림치즈볼로 맛과 식감을 다르게 즐길 수 있어요."],
        ["light", "가볍게 즐기는 먹태", ["a1", "a4"], "담백하고 쫄깃한 먹태에 부드러운 계란말이를 더해 식감을 균형 있게 구성했어요."],
        ["spicy", "매콤한 골뱅이 한 상", ["a2", "a4"], "새콤매콤한 골뱅이 소면에 부드러운 계란말이를 곁들여 매운맛을 쉬어 갈 수 있어요."],
        ["fire", "불향 가득 닭발 조합", ["a3", "d5"], "불향 나는 매콤한 닭발에 고소한 주먹밥을 더해 든든하게 즐길 수 있어요."],
        ["soup", "뜨끈한 국물 한 상", ["s2", "a8"], "시원한 어묵탕과 바삭한 해물파전으로 국물과 안주를 함께 즐길 수 있어요."],
        ["seafood", "얼큰한 해물 조합", ["s1", "c4"], "얼큰한 짬뽕탕에 바삭한 오징어 튀김을 곁들여 국물과 튀김의 식감을 살렸어요."],
        ["value", "알뜰하게 나누는 한 상", ["c3", "c7"], "쫄깃한 닭똥집과 고소한 치즈볼로 부담 적은 가격에 두 가지 안주를 즐길 수 있어요."],
        ["comfort", "고소하고 부드러운 조합", ["a4", "c7"], "부드러운 계란말이와 고소한 크림치즈볼로 맵지 않은 안주를 구성했어요."],
        ["dry", "건어물과 소시지 조합", ["a10", "a5"], "오래 나눠 먹기 좋은 건어물에 따뜻한 모둠 소시지를 곁들였어요."],
        ["ramen", "해장 라면 한 상", ["a4", "d7"], "부드러운 계란말이와 얼큰하게 끓인 라면으로 속을 든든하게 채울 수 있어요."],
        ["dooroochi", "두루치기 밥 한 상", ["s5", "d3"], "푹 익은 김치 두루치기에 공깃밥을 더해 든든한 한 끼 안주로 좋아요."],
        ["mussel", "시원한 홍합탕 조합", ["s4", "c4"], "시원한 홍합탕에 바삭한 오징어 튀김을 곁들여 국물과 튀김을 함께 즐길 수 있어요."],
    ],
    "drinks": {"맥주": "b1", "소주": "j1", "음료": "d2", "없이": None},
    "pair_meta": {
        "classic": {"kinds": ["fried"], "occasions": ["모임", "회식"], "mood": "hearty"},
        "garlic": {"kinds": ["fried"], "occasions": ["데이트", "모임"], "mood": None},
        "light": {"kinds": ["anju"], "occasions": ["가볍게", "데이트"], "mood": "light"},
        "spicy": {"kinds": ["anju"], "occasions": ["스트레스", "회식"], "mood": "hearty"},
        "fire": {"kinds": ["anju"], "occasions": ["스트레스"], "mood": None},
        "soup": {"kinds": ["soup"], "occasions": ["모임", "회식"], "mood": "hearty"},
        "seafood": {"kinds": ["seafood", "soup"], "occasions": ["스트레스", "회식"], "mood": "hearty"},
        "value": {"kinds": ["fried"], "occasions": ["가볍게", "모임"], "mood": None},
        "comfort": {"kinds": ["anju"], "occasions": ["가볍게", "데이트"], "mood": "light"},
        "dry": {"kinds": ["anju"], "occasions": ["가볍게", "모임"], "mood": "light"},
        "ramen": {"kinds": ["rice_noodle"], "occasions": ["가볍게"], "mood": "light"},
        "dooroochi": {"kinds": ["rice_noodle"], "occasions": ["회식"], "mood": "hearty"},
        "mussel": {"kinds": ["seafood", "soup"], "occasions": ["데이트", "모임"], "mood": None},
    },
    "hot_themed": ["dooroochi", "fire", "seafood", "spicy"],
    "kind_label": {"fried": "튀김·치킨", "anju": "안주", "soup": "탕·국물", "seafood": "해산물", "rice_noodle": "밥·면"},
    "intent_label": {"모임": "친구·모임", "회식": "회식", "데이트": "데이트", "가볍게": "가볍게 한잔", "스트레스": "스트레스 푸는 자리"},
}
