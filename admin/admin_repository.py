"""관리자 화면이 쓰는 모든 데이터의 단일 출입구.

구조: 화면(app.py) → AdminRepository(JSON → 화면용 표 변환, 한 곳) → Backend(더미 또는 서버)
 - DummyBackend(dummy_data.py): 서버와 똑같은 JSON 을 돌려주는 가짜 서버
 - ApiBackend: 실제 서버 호출 (아래 ENDPOINTS 가 경로 목록)
둘은 같은 메서드·같은 JSON 을 돌려주므로 화면 코드는 바꿀 필요가 없다.

데이터 소스 전환: 환경 변수 DATA_SOURCE
  dummy : 더미만 (서버 불필요, 로그인은 ADMIN_TOKEN 과 비교)
  api   : 서버만. 서버가 안 닿으면 로그인 실패
  auto  : 서버가 닿으면 API, 안 닿으면 더미 (기본값)

새 데이터를 API로 바꾸려면: ENDPOINTS 에 경로를 적고 → ApiBackend 와 DummyBackend 에 같은 이름의
메서드를 추가하고 → AdminRepository 에 표 변환을 추가한다.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from admin_dummy_data import DummyBackend, Unsupported  # noqa: E402
from shared import api  # noqa: E402

ENDPOINTS = {
    "store": "/api/store",
    "menus": "/admin/api/menus",              # GET {categories, menus} / PUT·DELETE /{id}
    "members": "/admin/api/members",          # GET ?repeat&regular&dormant
    "orders": "/admin/api/orders",
    "stats": "/admin/api/stats",
    "sms": "/admin/api/marketing/sms",        # /usage /preview /send /logs
    "opt_out": "/admin/api/members/{id}/opt-out",
}
KST = timezone(timedelta(hours=9))
SPICY_LABELS = {0: "안 매움", 1: "순한맛", 2: "보통맛", 3: "아주 매움"}
SPICY_VALUES = {v: k for k, v in SPICY_LABELS.items()}
MODES = ("dummy", "api", "auto")
GRADES = ["신규", "재방문", "단골", "휴면"]
DEFAULT_RULE = {"repeat": 2, "regular": 5, "dormant": 60}
MENU_COLUMNS = ["id", "메뉴명", "카테고리", "가격", "설명", "이미지 URL", "판매 여부", "매운 정도", "추천 가중치", "세트 가능"]


class ApiBackend:
    """서버 호출. 반환값은 서버가 준 JSON 그대로 (DummyBackend 와 같은 모양)."""
    source = "api"

    def __init__(self, token: str):
        self.token = token

    def login(self, token: str) -> bool:
        """토큰이 맞으면 True, 틀리면 False. 서버가 안 닿으면 ApiUnavailable."""
        try:
            api.get(ENDPOINTS["menus"], token)
            self.token = token
            return True
        except api.ApiError as e:
            if e.status == 401:
                return False
            raise

    def store(self):
        return api.get(ENDPOINTS["store"])

    def menus(self):
        return api.get(ENDPOINTS["menus"], self.token)

    def save_menu(self, menu_id, fields):
        return api.put(f"{ENDPOINTS['menus']}/{menu_id}", self.token, json=fields)

    def delete_menu(self, menu_id):
        return api.delete(f"{ENDPOINTS['menus']}/{menu_id}", self.token)

    def members(self, rule):
        return api.get(ENDPOINTS["members"], self.token, params=rule)

    def orders(self):
        return api.get(ENDPOINTS["orders"], self.token)

    def stats(self, rule):
        return api.get(ENDPOINTS["stats"], self.token)

    def sms_usage(self):
        return api.get(f"{ENDPOINTS['sms']}/usage", self.token)

    def sms_preview(self, grades, body):
        return api.post(f"{ENDPOINTS['sms']}/preview", self.token, json={"grades": grades, "body": body})

    def sms_send(self, grades, body):
        return api.post(f"{ENDPOINTS['sms']}/send", self.token, json={"grades": grades, "body": body})

    def sms_logs(self):
        return api.get(f"{ENDPOINTS['sms']}/logs", self.token)

    def opt_out(self, member_id):
        return api.post(ENDPOINTS["opt_out"].format(id=member_id), self.token)


class AdminRepository:
    """백엔드 JSON → 화면용 표/값. 더미든 서버든 같은 변환을 쓴다."""

    def __init__(self, backend):
        self.backend = backend

    @property
    def source(self) -> str:
        return self.backend.source

    # ---- 메뉴 ----
    def categories(self) -> list[dict]:
        return self.backend.menus()["categories"]

    def menus(self) -> pd.DataFrame:
        payload = self.backend.menus()
        names = {c["id"]: c["name"] for c in payload["categories"]}
        rows = [{"id": m["id"], "메뉴명": m["name"], "카테고리": names.get(m["cat"], m["cat"]), "가격": m["price"],
                 "설명": m["desc"], "이미지 URL": m["image_url"], "판매 여부": not m["soldout"],
                 "매운 정도": SPICY_LABELS.get(m["spicy"], "안 매움"), "추천 가중치": m["weight"], "세트 가능": m["set_ok"]}
                for m in payload["menus"]]
        return pd.DataFrame(rows, columns=MENU_COLUMNS)

    def save_menus(self, new: pd.DataFrame, old: pd.DataFrame) -> dict:
        """표에서 바뀐 행만 저장하고, 지워진 행은 삭제한다. {'saved': n, 'deleted': n}"""
        ids = {c["name"]: c["id"] for c in self.categories()}
        old_by_id = {r["id"]: r for r in old.to_dict("records")}
        saved, seen = 0, set()
        for row in new.to_dict("records"):
            menu_id = row["id"] if isinstance(row["id"], str) and row["id"] else f"m{uuid.uuid4().hex[:6]}"
            seen.add(menu_id)
            if old_by_id.get(menu_id) == {**row, "id": menu_id}:
                continue  # 바뀌지 않은 행
            self.backend.save_menu(menu_id, {
                "name": row["메뉴명"], "cat": ids[row["카테고리"]], "price": int(row["가격"]), "desc": _text(row["설명"]),
                "image_url": _text(row["이미지 URL"]), "soldout": not bool(row["판매 여부"]),
                "spicy": SPICY_VALUES.get(row["매운 정도"], 0), "weight": int(row["추천 가중치"]),
                "set_ok": bool(row["세트 가능"])})
            saved += 1
        deleted = [i for i in old_by_id if i not in seen]
        for menu_id in deleted:
            self.backend.delete_menu(menu_id)
        return {"saved": saved, "deleted": len(deleted)}

    # ---- 고객 / 주문 / 통계 ----
    def members(self, rule: dict | None = None) -> pd.DataFrame:
        rows = self.backend.members(rule or DEFAULT_RULE)["members"]
        return pd.DataFrame([{
            "customer_id": m["id"], "닉네임": m["nickname"], "성별": m["gender"], "연령대": m["age_group"],
            "방문 횟수": m["visit_count"], "마지막 방문일": _kst_date(m["last_visit_at"]),
            "마케팅 수신 동의": m["marketing_consent"], "수신거부": m["opted_out"], "등급": m["grade"]} for m in rows],
            columns=["customer_id", "닉네임", "성별", "연령대", "방문 횟수", "마지막 방문일", "마케팅 수신 동의", "수신거부", "등급"])

    def orders(self) -> pd.DataFrame:
        rows = self.backend.orders()
        return pd.DataFrame([{
            "order_id": f"O{o['id']:04d}", "주문 시각": datetime.fromisoformat(o["ts"]).astimezone(KST).replace(tzinfo=None),
            "customer_id": o["member_id"], "닉네임": o.get("nickname") or "비회원", "테이블": o["table_no"],
            "주문 내역": ", ".join(f"{l['name']} x{l['qty']}" for l in o["lines"]), "금액": o["total"],
            "AI 추천 사용": o["ai_combo"]} for o in rows],
            columns=["order_id", "주문 시각", "customer_id", "닉네임", "테이블", "주문 내역", "금액", "AI 추천 사용"])

    def stats(self, rule: dict | None = None) -> dict:
        return self.backend.stats(rule or DEFAULT_RULE)

    # ---- 마케팅 (서버 필요) ----
    def __getattr__(self, name):  # sms_usage, sms_preview, sms_send, sms_logs, opt_out 은 백엔드로 위임
        if name.startswith("sms_") or name == "opt_out":
            return getattr(self.backend, name)
        raise AttributeError(name)


def _text(value) -> str:
    """표의 빈 칸(None/NaN)은 빈 문자열로 보낸다. (NaN 은 JSON 으로 보낼 수 없다)"""
    return "" if value is None or pd.isna(value) else str(value)


def _kst_date(iso: str | None):
    return datetime.fromisoformat(iso).astimezone(KST).date() if iso else None


def data_source_mode() -> str:
    mode = os.getenv("DATA_SOURCE", "auto").strip().lower()
    return mode if mode in MODES else "auto"


class LoginResult:
    def __init__(self, repo=None, error: str | None = None, notice: str | None = None):
        self.repo, self.error, self.notice = repo, error, notice


def connect(token: str) -> LoginResult:
    """DATA_SOURCE 에 맞게 토큰을 확인하고 저장소를 만든다."""
    mode = data_source_mode()
    dummy = AdminRepository(DummyBackend())
    if mode == "dummy":
        return LoginResult(dummy) if dummy.backend.login(token) else LoginResult(error="토큰이 올바르지 않습니다.")
    backend = ApiBackend(token)
    try:
        if backend.login(token):
            return LoginResult(AdminRepository(backend))
        return LoginResult(error="토큰이 올바르지 않습니다.")
    except api.ApiUnavailable:
        if mode == "api":
            return LoginResult(error="서버에 연결할 수 없습니다. 백엔드가 실행 중인지 확인해 주세요.")
    # auto: 서버가 없으면 더미로 연다
    if not dummy.backend.login(token):
        return LoginResult(error="토큰이 올바르지 않습니다.")
    return LoginResult(dummy, notice="서버에 연결할 수 없어 더미 데이터로 표시하고 있어요.")
