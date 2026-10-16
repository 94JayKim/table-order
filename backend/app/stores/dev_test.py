"""개발용 DB 왕복 확인 저장소.

서비스 데이터와 분리된 `test` 테이블에 임의 값을 넣고 다시 읽어,
현재 서버가 연결된 DB에 실제로 쓰기·읽기가 되는지 확인한다.
"""

import uuid

from app.stores.db import Database


class DevTestStore:
    def __init__(self, db: Database):
        self.db = db

    def round_trip(self) -> dict:
        """임의 값을 INSERT 한 뒤 같은 id로 SELECT 해서 결과를 반환한다."""
        test_id = str(uuid.uuid4())
        value = str(uuid.uuid4())
        try:
            self.db.run("INSERT INTO test (id, value) VALUES (?, ?)", (test_id, value))
            row = self.db.one("SELECT value FROM test WHERE id=?", (test_id,))
        except Exception as exc:  # 화면에는 비밀 정보 대신 오류 종류만 보여 준다.
            return {"result": 0, "reason": type(exc).__name__}

        if row and row["value"] == value:
            return {"result": 1}
        return {"result": 0, "reason": "저장한 값과 읽은 값이 다릅니다."}
