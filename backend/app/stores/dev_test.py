"""개발 흐름 확인 버튼이 사용하는 test 테이블 저장소."""

import secrets

from app.stores.db import Database


class DevTestStore:
    def __init__(self, db: Database):
        self.db = db

    def insert_and_check(self) -> bool:
        """임의 값을 저장한 뒤 같은 행을 읽어 DB 쓰기·읽기를 함께 확인한다."""
        value = secrets.token_hex(8)
        row_id = self.db.run("INSERT INTO test (value) VALUES (?)", (value,))
        row = self.db.one("SELECT value FROM test WHERE id=?", (row_id,))
        return bool(row and row["value"] == value)
