"""화면용 콘텐츠(카테고리·룰렛·질문·추천 규칙 등) 저장소. 모양은 user/*_data.py 더미와 같다."""

import json
from pathlib import Path

from app.stores.db import Database

SEED = Path(__file__).resolve().parent.parent / "seed" / "content.json"
NAMES = ("categories", "roulette_prizes", "staff_calls", "quiz_questions", "weather", "rules")
SCHEMA = "CREATE TABLE IF NOT EXISTS content (name TEXT PRIMARY KEY, data TEXT NOT NULL)"


class ContentStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        for name in NAMES:  # 이미 있는 항목(관리자가 고친 것)은 덮어쓰지 않는다
            if not db.one("SELECT 1 FROM content WHERE name=?", (name,)):
                self.set(name, seed[name])

    def get(self, name: str):
        row = self.db.one("SELECT data FROM content WHERE name=?", (name,))
        return json.loads(row["data"]) if row else None

    def all(self) -> dict:
        return {name: self.get(name) for name in NAMES}

    def set(self, name: str, data) -> None:
        self.db.run("INSERT INTO content (name, data) VALUES (?, ?) "
                    "ON CONFLICT(name) DO UPDATE SET data=excluded.data",
                    (name, json.dumps(data, ensure_ascii=False)))
