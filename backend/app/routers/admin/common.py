"""관리자 라우터들이 같이 쓰는 도우미."""

from app.core.settings import Settings


def grade_rule(s: Settings, repeat=None, regular=None, dormant=None) -> dict:
    return {"repeat": repeat or s.grade_repeat_visits, "regular": regular or s.grade_regular_visits,
            "dormant": dormant or s.grade_dormant_days}
