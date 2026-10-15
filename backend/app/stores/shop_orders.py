"""주문 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다). 주문 스키마를 바꾸면 통계(B 담당)도 확인한다."""

import json

from app.stores.members import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, member_id INTEGER,
    lines TEXT NOT NULL, total INTEGER NOT NULL, ai_combo INTEGER NOT NULL DEFAULT 0);
"""


class OrderMixin:
    def add_order(self, table_no: int, lines: list[dict], total: int, member_id: int | None) -> dict:
        ai = int(any(str(l.get("id", "")).startswith("combo:") for l in lines))
        oid = self.db.run("INSERT INTO orders (ts, table_no, member_id, lines, total, ai_combo) VALUES (?,?,?,?,?,?)",
                          (now_iso(), table_no, member_id, json.dumps(lines, ensure_ascii=False), total, ai))
        return self.order(oid)

    @staticmethod
    def _order(r: dict) -> dict:
        r["lines"] = json.loads(r["lines"])
        r["ai_combo"] = bool(r["ai_combo"])
        return r

    def order(self, order_id: int) -> dict:
        return self._order(self.db.one("SELECT * FROM orders WHERE id=?", (order_id,)))

    def orders(self, member_id: int | None = None) -> list[dict]:
        if member_id is None:
            rows = self.db.all("SELECT * FROM orders ORDER BY id DESC")
        else:
            rows = self.db.all("SELECT * FROM orders WHERE member_id=? ORDER BY id DESC", (member_id,))
        return [self._order(r) for r in rows]
