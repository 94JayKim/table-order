"""추천 기록 저장소 (shop.py 의 ShopStore 가 합쳐 쓴다)."""

import json

from app.stores.members import now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, table_no INTEGER NOT NULL, member_id INTEGER,
    params TEXT NOT NULL, combo_ids TEXT NOT NULL);
"""


class RecommendationMixin:
    def add_recommendation(self, table_no: int, member_id: int | None, params: dict, combo_ids: list[str]) -> int:
        return self.db.run(
            "INSERT INTO recommendation_events (ts, table_no, member_id, params, combo_ids) VALUES (?,?,?,?,?)",
            (now_iso(), table_no, member_id, json.dumps(params, ensure_ascii=False), json.dumps(combo_ids)))

    def recommendation_count(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM recommendation_events")["n"]
