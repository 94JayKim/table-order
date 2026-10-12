"""관리자 화면용 더미 데이터 — '서버와 똑같은 JSON'을 돌려주는 가짜 서버(DummyBackend).

반환 모양은 백엔드 /admin/api/* 응답과 같다. 그래서 화면과 변환 코드(admin_repository.py)는
데이터가 더미인지 서버인지 모르고, DATA_SOURCE 만 바꾸면 전환된다.
"""
import random
from datetime import date, datetime, timedelta, timezone

TODAY = date(2026, 10, 12)
GRADES = ["신규", "재방문", "단골", "휴면"]
AGE_GROUPS = ["20대 미만", "20대", "30대", "40대", "50대 이상"]

# 손님 화면의 카테고리 콘텐츠와 같은 모양 (id, icon, name, colors). 서버에는 AI 추천 조합·인기메뉴 같은 가상 카테고리도 섞여 있다.
CATEGORIES = [
    {"id": "chicken", "icon": "🍗", "name": "치킨·튀김", "colors": ["#f6b93b", "#e55039"]},
    {"id": "anju", "icon": "🍢", "name": "안주", "colors": ["#b8e994", "#38ada9"]},
    {"id": "soup", "icon": "🍲", "name": "탕·전골", "colors": ["#ff6b6b", "#7d1d3f"]},
    {"id": "beer", "icon": "🍺", "name": "맥주", "colors": ["#fbc531", "#c27c0e"]},
    {"id": "soju", "icon": "🍶", "name": "소주·막걸리", "colors": ["#74b9ff", "#2d3a8c"]},
    {"id": "side", "icon": "🥤", "name": "음료·사이드", "colors": ["#a29bfe", "#4b3f9e"]},
]


def _menu(id_, cat, name, price, spicy=0, soldout=False, weight=50, set_ok=True, desc=""):
    return {"id": id_, "cat": cat, "name": name, "desc": desc, "price": price, "emoji": "🍽️", "tags": [],
            "soldout": soldout, "spicy": spicy, "weight": weight, "set_ok": set_ok, "image_url": ""}


MENUS = [
    _menu("c1", "chicken", "역전 옛날통닭 (한 마리·후라이드)", 18000, desc="겉은 바삭, 속은 촉촉한 가마솥 통닭"),
    _menu("c2", "chicken", "간장마늘 치킨", 20000, desc="달콤짭짤 간장에 마늘 듬뿍"),
    _menu("c3", "chicken", "닭똥집 튀김", 11000, desc="쫄깃한 식감, 맥주 도둑"),
    _menu("a1", "anju", "먹태구이", 14000, desc="청양마요 소스와 함께"),
    _menu("a2", "anju", "골뱅이 소면 무침 (보통맛)", 17000, spicy=2),
    _menu("a3", "anju", "직화 무뼈닭발 (아주 매운맛)", 18000, spicy=3),
    _menu("a4", "anju", "계란말이", 10000),
    _menu("a11", "anju", "노가리 구이", 9000, soldout=True),
    _menu("s1", "soup", "나가사키 짬뽕탕", 16000, spicy=2),
    _menu("s2", "soup", "어묵탕", 12000),
    _menu("b1", "beer", "생맥주 500cc", 4500, set_ok=False),
    _menu("j1", "soju", "참이슬", 5000, set_ok=False),
    _menu("d1", "side", "콜라", 2000, set_ok=False),
]


class Unsupported(Exception):
    """더미 모드에서는 쓸 수 없는 기능 (예: 실제 문자 발송)."""


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def _grade(visits: int, last: date, rule: dict) -> str:
    if (TODAY - last).days >= rule["dormant"]:
        return "휴면"
    return "단골" if visits >= rule["regular"] else "재방문" if visits >= rule["repeat"] else "신규"


def _age_group(year: int) -> str:
    age = TODAY.year - year
    return "20대 미만" if age < 20 else "20대" if age < 30 else "30대" if age < 40 else "40대" if age < 50 else "50대 이상"


class DummyBackend:
    """서버(ApiBackend)와 같은 메서드·같은 JSON. 상태는 이 객체(= 화면 세션) 안에만 있다."""
    source = "dummy"

    def __init__(self, seed: int = 7):
        r = random.Random(seed)
        self.menus_ = [dict(m) for m in MENUS]
        self.categories_ = [dict(c) for c in CATEGORIES]
        self.members_ = []
        for i in range(1, 61):
            self.members_.append({
                "id": i, "nickname": f"손님{i:02d}", "gender": r.choice(["남", "여"]),
                "birth_year": r.choice([2008, 1998, 1992, 1984, 1975]),
                "visit_count": r.choice([1, 1, 1, 2, 2, 3, 4, 5, 6, 8, 12]),
                "last_visit": TODAY - timedelta(days=r.choice([0, 1, 2, 3, 5, 8, 14, 21, 35, 50, 70, 95, 130])),
                "marketing_consent": r.random() < 0.7, "opted_out": False})
        self.orders_ = []
        for i in range(1, 301):
            picks = r.sample([m for m in MENUS if not m["soldout"]], r.randint(2, 4))
            lines = [{"id": m["id"], "name": m["name"], "opt": "", "unit": m["price"], "qty": r.randint(1, 2)} for m in picks]
            day = TODAY - timedelta(days=0 if i <= 28 else r.randint(1, 29))
            ts = datetime(day.year, day.month, day.day, tzinfo=timezone(timedelta(hours=9))) + timedelta(minutes=r.randint(1020, 1430))
            self.orders_.append({"id": i, "ts": _iso(ts), "table_no": r.randint(1, 30), "member_id": r.choice(self.members_)["id"],
                                 "lines": lines, "total": sum(l["unit"] * l["qty"] for l in lines),
                                 "ai_combo": r.random() < 0.45})
        self.orders_.sort(key=lambda o: o["ts"], reverse=True)

    # ---- 로그인 / 매장 -----------------------------------------------------
    def login(self, token: str) -> bool:
        import os
        return token == os.getenv("ADMIN_TOKEN", "change-me")

    def store(self) -> dict:
        return {"name": "역전할머니맥주", "branch": "홍대점", "slogan": "", "tables": 30}

    # ---- 메뉴 ----------------------------------------------------------------
    def menus(self) -> dict:
        return {"categories": [{"id": c["id"], "name": c["name"]} for c in self.categories_],
                "menus": [dict(m) for m in self.menus_]}

    def categories_full(self) -> list:
        return [dict(c) for c in self.categories_]

    def save_categories(self, categories: list) -> list:
        self.categories_ = [dict(c) for c in categories]
        return self.categories_full()

    def save_menu(self, menu_id: str, fields: dict) -> dict:
        cur = next((m for m in self.menus_ if m["id"] == menu_id), None)
        if cur is None:
            cur = _menu(menu_id, fields["cat"], fields["name"], fields["price"])
            self.menus_.append(cur)
        cur.update(fields)
        return dict(cur)

    def delete_menu(self, menu_id: str) -> None:
        self.menus_ = [m for m in self.menus_ if m["id"] != menu_id]

    # ---- 고객 / 주문 / 통계 --------------------------------------------------------
    def members(self, rule: dict) -> dict:
        return {"rule": rule, "members": [{
            "id": m["id"], "nickname": m["nickname"], "gender": m["gender"], "age_group": _age_group(m["birth_year"]),
            "visit_count": m["visit_count"], "last_visit_at": _iso(datetime.combine(m["last_visit"], datetime.min.time(), timezone.utc)),
            "marketing_consent": m["marketing_consent"], "opted_out": m["opted_out"], "has_phone": m["marketing_consent"],
            "grade": _grade(m["visit_count"], m["last_visit"], rule)} for m in self.members_]}

    def orders(self) -> list:
        nick = {m["id"]: m["nickname"] for m in self.members_}
        return [{**o, "nickname": nick.get(o["member_id"])} for o in self.orders_]

    def stats(self, rule: dict) -> dict:
        today = [o for o in self.orders_ if o["ts"][:10] >= TODAY.isoformat()]  # UTC 기준 근사
        members = {m["id"]: m for m in self.members(rule)["members"]}
        grades = {o["member_id"]: members[o["member_id"]]["grade"] for o in today}
        counts: dict[str, int] = {}
        for o in self.orders_:
            for l in o["lines"]:
                counts[l["name"]] = counts.get(l["name"], 0) + l["qty"]
        ai = sum(1 for o in self.orders_ if o["ai_combo"])
        shown = len(self.orders_) * 2  # 더미: 추천 노출 수
        age: dict[str, int] = {k: 0 for k in AGE_GROUPS}
        gender: dict[str, int] = {}
        for m in members.values():
            age[m["age_group"]] += 1
            gender[m["gender"]] = gender.get(m["gender"], 0) + 1
        return {"today_orders": len(today), "avg_order_amount": int(sum(o["total"] for o in today) / len(today)) if today else 0,
                "new_customers": sum(1 for g in grades.values() if g == "신규"),
                "returning_customers": sum(1 for g in grades.values() if g in ("재방문", "단골")),
                "age_groups": age, "genders": gender,
                "popular_menus": [{"name": n, "qty": q} for n, q in sorted(counts.items(), key=lambda kv: -kv[1])[:10]],
                "ai": {"recommendations": shown, "ai_orders": ai, "hit_rate": round(ai / shown, 3),
                       "definition": "AI 조합이 포함된 주문 수 / 추천이 노출된 횟수 (임시 기준)"}}

    # ---- 문자 발송: 실제 발송은 서버가 필요하다 ----------------------------------------
    def _no_sms(self, *a, **kw):
        raise Unsupported("문자 발송은 서버(DATA_SOURCE=api)가 필요해요.")

    sms_usage = sms_preview = sms_send = sms_logs = opt_out = _no_sms
