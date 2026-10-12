"""메뉴·주문·직원 호출·추천 기록 저장소."""

import json
from pathlib import Path

from app.stores.db import Database
from app.stores.members import now_iso

SEED = Path(__file__).resolve().parent.parent / "seed" / "menu.json"
MENU_FIELDS = ("name", "cat", "price", "desc", "image_url", "soldout", "spicy", "weight", "set_ok", "emoji", "tags")

SCHEMA = """
CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY, cat TEXT NOT NULL, name TEXT NOT NULL, desc TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL, emoji TEXT NOT NULL DEFAULT '🍽️', tags TEXT NOT NULL DEFAULT '[]',
    soldout INTEGER NOT NULL DEFAULT 0, spicy INTEGER NOT NULL DEFAULT 0, weight INTEGER NOT NULL DEFAULT 50,
    set_ok INTEGER NOT NULL DEFAULT 0, image_url TEXT NOT NULL DEFAULT '', sort INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, member_id INTEGER,
    lines TEXT NOT NULL, total INTEGER NOT NULL, ai_combo INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, items TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS recommendation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, member_id INTEGER,
    params TEXT NOT NULL, combo_ids TEXT NOT NULL);
"""


def _menu(row: dict) -> dict:
    row["tags"] = json.loads(row["tags"])
    for k in ("soldout", "set_ok"):
        row[k] = bool(row[k])
    return row


class ShopStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        if not db.one("SELECT 1 FROM menus LIMIT 1"):
            for i, m in enumerate(json.loads(SEED.read_text(encoding="utf-8"))):
                self.save_menu(m["id"], m, sort=i)

    # ---- 메뉴
    def menus(self) -> list[dict]:
        return [_menu(r) for r in self.db.all("SELECT * FROM menus ORDER BY sort, id")]

    def menu(self, menu_id: str) -> dict | None:
        r = self.db.one("SELECT * FROM menus WHERE id=?", (menu_id,))
        return _menu(r) if r else None

    def save_menu(self, menu_id: str, fields: dict, sort: int | None = None) -> dict:
        """있으면 주어진 필드만 수정, 없으면 새로 만든다."""
        cur = self.menu(menu_id)
        data = {**(cur or {"desc": "", "emoji": "🍽️", "tags": [], "soldout": False, "spicy": 0, "weight": 50,
                           "set_ok": False, "image_url": ""}), **{k: v for k, v in fields.items() if k in MENU_FIELDS}}
        if sort is None:
            row = self.db.one("SELECT sort FROM menus WHERE id=?", (menu_id,))
            sort = row["sort"] if row else (self.db.one("SELECT COALESCE(MAX(sort),0)+1 AS n FROM menus")["n"])
        self.db.run(
            """INSERT INTO menus (id, cat, name, desc, price, emoji, tags, soldout, spicy, weight, set_ok, image_url, sort)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET cat=excluded.cat, name=excluded.name, desc=excluded.desc,
                 price=excluded.price, emoji=excluded.emoji, tags=excluded.tags, soldout=excluded.soldout,
                 spicy=excluded.spicy, weight=excluded.weight, set_ok=excluded.set_ok, image_url=excluded.image_url""",
            (menu_id, data["cat"], data["name"], data["desc"], data["price"], data["emoji"],
             json.dumps(data["tags"], ensure_ascii=False), int(data["soldout"]), data["spicy"], data["weight"],
             int(data["set_ok"]), data["image_url"], sort))
        return self.menu(menu_id)

    def delete_menu(self, menu_id: str) -> bool:
        existed = self.menu(menu_id) is not None
        self.db.run("DELETE FROM menus WHERE id=?", (menu_id,))
        return existed

    # ---- 주문
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

    # ---- 직원 호출
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

    # ---- 추천 기록 (AI 추천 적중률 계산용)
    def add_recommendation(self, table_no: int, member_id: int | None, params: dict, combo_ids: list[str]) -> int:
        return self.db.run(
            "INSERT INTO recommendation_events (ts, table_no, member_id, params, combo_ids) VALUES (?,?,?,?,?)",
            (now_iso(), table_no, member_id, json.dumps(params, ensure_ascii=False), json.dumps(combo_ids)))

    def recommendation_count(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM recommendation_events")["n"]
