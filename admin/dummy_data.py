"""관리자 화면용 더미 데이터 (메뉴는 user/menu_data.py 를 그대로 사용)."""

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "user"))

import pandas as pd

from menu_data import CATEGORY_BY_ID, MENU

TODAY = date(2026, 10, 12)
AGE_GROUPS = ["20대", "30대", "40대", "50대 이상"]
GRADES = ["신규", "재방문", "단골", "휴면"]
SPICY_LABELS = {0: "안 매움", 1: "순한맛", 2: "보통맛", 3: "아주 매움"}


def _spicy(m):
    name = m["name"]
    if "아주 매운맛" in name:
        return 3
    if "보통맛" in name or "매운맛" in m["tags"]:
        return 2
    if "순한맛" in name:
        return 1
    return 0


def menu_frame() -> pd.DataFrame:
    rows = []
    for m in MENU:
        cat = CATEGORY_BY_ID[m["cat"]][2]
        rows.append({
            "id": m["id"], "메뉴명": m["name"], "카테고리": cat, "가격": m["price"],
            "설명": m["desc"], "이미지 URL": "", "판매 여부": not m["soldout"],
            "매운 정도": SPICY_LABELS[_spicy(m)],
            "추천 가중치": 50,
            "세트 가능": m["cat"] in ("chicken", "anju", "soup"),
        })
    return pd.DataFrame(rows)


def make_customers(n=60, seed=7) -> pd.DataFrame:
    r = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        visits = r.choice([1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 12])
        last = TODAY - timedelta(days=r.choice([0, 1, 2, 3, 5, 8, 14, 21, 35, 50, 70, 95, 130]))
        rows.append({
            "customer_id": f"C{i:03d}", "닉네임": f"손님{i:02d}",
            "성별": r.choice(["남", "여"]), "연령대": r.choice(AGE_GROUPS),
            "방문 횟수": visits, "마지막 방문일": last,
            "마케팅 수신 동의": r.random() < 0.7,
        })
    return pd.DataFrame(rows)


def make_orders(customers: pd.DataFrame, n=300, seed=11) -> pd.DataFrame:
    r = random.Random(seed)
    sellable = [m for m in MENU if not m["soldout"]]
    cids = list(customers["customer_id"])
    rows = []
    for i in range(1, n + 1):
        picks = r.sample(sellable, r.randint(2, 5))
        items = {m["name"]: r.randint(1, 2) for m in picks}
        total = sum(m["price"] * items[m["name"]] for m in picks)
        day = TODAY - timedelta(days=0 if i <= 28 else r.randint(1, 29))
        rows.append({
            "order_id": f"O{i:04d}", "주문 시각": datetime.combine(day, datetime.min.time()) + timedelta(minutes=r.randint(17 * 60, 24 * 60 - 1)),
            "customer_id": r.choice(cids), "테이블": r.randint(1, 30),
            "주문 내역": ", ".join(f"{k} x{v}" for k, v in items.items()),
            "금액": total, "AI 추천 사용": r.random() < 0.45,
        })
    return pd.DataFrame(rows).sort_values("주문 시각", ascending=False).reset_index(drop=True)
