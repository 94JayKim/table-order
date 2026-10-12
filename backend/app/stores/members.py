"""회원 저장소 (SQLite, 표준 라이브러리). 프로토타입용 단일 연결."""

import sqlite3
import threading
from datetime import datetime, timezone

COLUMNS = ("id", "kakao_id", "nickname", "phone", "gender", "birthday", "marketing_consent",
           "marketing_consent_at", "opted_out", "visit_count", "last_visit_at", "created_at")


def _path(database_url: str) -> str:
    return database_url.removeprefix("sqlite:///") or ":memory:"


class MemberStore:
    def __init__(self, database_url: str = "sqlite:///:memory:"):
        self._db = sqlite3.connect(_path(database_url), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("""CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT, kakao_id TEXT UNIQUE NOT NULL, nickname TEXT NOT NULL,
                phone TEXT, gender TEXT, birthday TEXT,
                marketing_consent INTEGER NOT NULL DEFAULT 0, marketing_consent_at TEXT,
                opted_out INTEGER NOT NULL DEFAULT 0,
                visit_count INTEGER NOT NULL DEFAULT 0, last_visit_at TEXT, created_at TEXT NOT NULL)""")
            self._db.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def upsert_login(self, kakao_id: str, nickname: str, gender: str | None = None,
                     birthday: str | None = None) -> dict:
        """카카오 로그인 때마다 호출: 없으면 가입, 있으면 방문 횟수와 마지막 방문일을 갱신."""
        now = self._now()
        with self._lock:
            self._db.execute(
                """INSERT INTO members (kakao_id, nickname, gender, birthday, visit_count, last_visit_at, created_at)
                   VALUES (?, ?, ?, ?, 1, ?, ?)
                   ON CONFLICT(kakao_id) DO UPDATE SET nickname=excluded.nickname,
                     gender=COALESCE(excluded.gender, gender), birthday=COALESCE(excluded.birthday, birthday),
                     visit_count=visit_count+1, last_visit_at=excluded.last_visit_at""",
                (kakao_id, nickname, gender, birthday, now, now))
            self._db.commit()
        return self.get_by_kakao(kakao_id)

    def get_by_kakao(self, kakao_id: str) -> dict:
        with self._lock:
            row = self._db.execute("SELECT * FROM members WHERE kakao_id=?", (kakao_id,)).fetchone()
        return dict(row)

    def get(self, member_id: int) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()
        return dict(row) if row else None

    def update_profile(self, member_id: int, phone: str | None, marketing_consent: bool | None) -> dict | None:
        with self._lock:
            if phone is not None:
                self._db.execute("UPDATE members SET phone=? WHERE id=?", (phone, member_id))
            if marketing_consent is not None:
                self._db.execute(
                    "UPDATE members SET marketing_consent=?, marketing_consent_at=? WHERE id=?",
                    (int(marketing_consent), self._now() if marketing_consent else None, member_id))
            self._db.commit()
        return self.get(member_id)
