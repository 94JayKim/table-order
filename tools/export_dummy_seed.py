"""user 페이지의 더미 데이터를 백엔드 시드(JSON)로 내보낸다.

더미 파일이 곧 API 응답 명세이므로, 이 도구로 서버 초기 데이터를 만들면 둘이 어긋나지 않는다.
실행: python tools/export_dummy_seed.py   (저장소 루트에서)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "user"))

import ai_quiz_data  # noqa: E402
import menu_data  # noqa: E402
import recommendation_data  # noqa: E402

content = {
    "categories": menu_data.CATEGORIES,
    "roulette_prizes": menu_data.ROULETTE_PRIZES,
    "staff_calls": menu_data.STAFF_CALLS,
    "quiz_questions": ai_quiz_data.QUESTIONS,
    "weather": ai_quiz_data.WEATHER,
    "rules": recommendation_data.RULES,
}
out = ROOT / "backend" / "app" / "seed" / "content.json"
out.write_text(json.dumps(content, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{out.relative_to(ROOT)}: {', '.join(content)}")
