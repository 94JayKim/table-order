"""SQLite 연결 공용 래퍼 (프로토타입: 단일 연결 + 락). 저장소들이 같은 DB를 나눠 쓴다."""

import sqlite3
import threading


class Database:
    def __init__(self, database_url: str = "sqlite:///:memory:"):
        path = database_url.removeprefix("sqlite:///") or ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()

    def run(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur.lastrowid

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def script(self, sql: str) -> None:
        with self._lock:
            self._conn.executescript(sql)
            self._conn.commit()
