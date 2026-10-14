"""직원 호출 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다)."""

import json

from app.stores.members import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, items TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0);
"""


class CallMixin:
    def add_call(self, table_no: int, items: list[str]) -> dict:
        cid = self.db.run("INSERT INTO calls (ts, table_no, items) VALUES (?,?,?)",
                          (now_iso(), table_no, json.dumps(items, ensure_ascii=False)))
        return self.call(cid)

    def call(self, call_id: int) -> dict:
        r = self.db.one("SELECT * FROM calls WHERE id=?", (call_id,))
        r["items"], r["done"] = json.loads(r["items"]), bool(r["done"])
        return r

    def calls(self) -> list[dict]:
        return [self.call(r["id"]) for r in self.db.all("SELECT id FROM calls ORDER BY id DESC")]

    def finish_call(self, call_id: int) -> dict | None:
        if not self.db.one("SELECT 1 FROM calls WHERE id=?", (call_id,)):
            return None
        self.db.run("UPDATE calls SET done=1 WHERE id=?", (call_id,))
        return self.call(call_id)
