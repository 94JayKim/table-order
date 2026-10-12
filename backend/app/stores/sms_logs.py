"""문자 발송 로그. 월 사용량(무료 한도 관리)도 여기서 집계한다."""

from app.stores.db import Database
from app.stores.members import now_iso

SCHEMA = """CREATE TABLE IF NOT EXISTS sms_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, month TEXT NOT NULL, request_id TEXT,
    type TEXT NOT NULL, content TEXT NOT NULL, target_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT)"""


class SmsLogStore:
    def __init__(self, db: Database):
        self.db = db
        db.script(SCHEMA)

    def add(self, month: str, kind: str, content: str, count: int, status: str,
            request_id: str | None = None, error: str | None = None) -> int:
        return self.db.run(
            "INSERT INTO sms_logs (ts, month, request_id, type, content, target_count, status, error) VALUES (?,?,?,?,?,?,?,?)",
            (now_iso(), month, request_id, kind, content, count, status, error))

    def usage(self, month: str) -> dict:
        """실패한 발송은 한도에서 제외한다. dry_run 은 실제 호출이 아니지만 한도 검증을 위해 센다."""
        rows = self.db.all("SELECT type, COALESCE(SUM(target_count),0) AS n FROM sms_logs "
                           "WHERE month=? AND status IN ('sent','dry_run') GROUP BY type", (month,))
        used = {"SMS": 0, "LMS": 0}
        used.update({r["type"]: r["n"] for r in rows})
        return used

    def logs(self, limit: int = 100) -> list[dict]:
        return self.db.all("SELECT * FROM sms_logs ORDER BY id DESC LIMIT ?", (limit,))
