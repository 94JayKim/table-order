"""AI 질문(회의록 2.4)의 더미 데이터: 질문·선택지, 자동 활용 데이터(날씨·시간대).

질문 순서: 고객 상태(배고픔·스트레스) → 방문 인원(인원수·성비) → 음식 취향(종류·맵기) → 방문 상황(의도) → 소비 조건(예산).
정식 구현에서는 이 목록을 서버/관리자 설정에서 불러오고, 날씨는 날씨 API, 시간대는 서버 시각을 쓴다.
"""
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

# 각 선택지: (값, 라벨, 이모지). value 는 추천 로직(recommendations.py)이 이해하는 값이다.
QUESTIONS = [
    {"id": "hunger", "group": "고객 상태", "title": "지금 얼마나 배고프세요?", "cols": 3,
     "options": [("출출해요", "조금 출출해요", "🙂"), ("적당해요", "적당해요", "😋"), ("매우 배고파요", "매우 배고파요", "🤤")]},
    {"id": "stress", "group": "고객 상태", "title": "오늘 스트레스 지수는 어느 정도예요?", "cols": 3,
     "options": [("낮음", "낮아요", "😊"), ("보통", "보통이에요", "😐"), ("높음", "높아요", "😤")]},
    {"id": "people", "group": "방문 인원", "title": "함께 오신 분은 몇 명인가요?", "cols": 3,
     "options": [(1, "1명", "🧑"), (2, "2명", "👫"), (3, "3명", "👨‍👩‍👦"), (4, "4명", "👨‍👩‍👧‍👦"), (5, "5명 이상", "🧑‍🤝‍🧑")]},
    {"id": "gender", "group": "방문 인원", "title": "일행의 성별은 어떻게 되나요?", "cols": 3,
     "options": [("남자만", "남자끼리", "👨"), ("여자만", "여자끼리", "👩"), ("혼성", "남녀 함께", "👫")]},
    {"id": "kind", "group": "음식 취향", "title": "어떤 종류가 끌리세요?", "cols": 3,
     "options": [("fried", "튀김·치킨", "🍗"), ("anju", "안주류", "🍢"), ("soup", "탕·국물", "🍲"),
                 ("seafood", "해산물", "🦑"), ("rice_noodle", "밥·면", "🍜"), ("any", "상관없어요", "🍽️")]},
    {"id": "spicy", "group": "음식 취향", "title": "맵기는 어느 정도가 좋으세요?", "cols": 3,
     "options": [("맵지 않게", "맵지 않게", "🥛"), ("상관없어요", "보통이면 좋아요", "🌶️"), ("매콤하게", "매콤하게!", "🔥")]},
    {"id": "intent", "group": "방문 상황", "title": "오늘 방문 목적은 무엇인가요?", "cols": 3,
     "options": [("모임", "친구·모임", "🍻"), ("회식", "회식", "🥂"), ("데이트", "데이트", "💕"),
                 ("가볍게", "가볍게 한잔", "🍺"), ("스트레스", "스트레스 풀러", "💥")]},
    {"id": "budget", "group": "소비 조건", "title": "예산은 얼마까지 생각하세요?", "cols": 3,
     "options": [(30000, "3만원 이하", "💵"), (50000, "5만원 이하", "💴"), (70000, "7만원 이하", "💶"),
                 (100000, "10만원 이하", "💷"), (150000, "상관없어요", "💎")]},
]
QUESTION_BY_ID = {q["id"]: q for q in QUESTIONS}

# 자동 활용 데이터 (더미). 주소의 ?weather=rain 으로 바꿔 볼 수 있다: sunny / rain / snow / hot / cloudy
WEATHER = {"sunny": ("맑음", "☀️"), "cloudy": ("흐림", "☁️"), "rain": ("비", "🌧️"), "snow": ("눈", "❄️"), "hot": ("무더위", "🥵")}
DUMMY_WEATHER = "sunny"


def current_weather(override: str | None = None) -> str:
    return override if override in WEATHER else DUMMY_WEATHER


def time_slot(now: datetime | None = None) -> tuple[int, str]:
    """(시, 시간대 이름)."""
    h = (now or datetime.now(KST)).hour
    name = ("새벽" if h < 5 else "점심" if h < 11 else "오후" if h < 17 else "저녁" if h < 22 else "심야")
    return h, name


def answer_label(qid: str, value) -> str:
    for v, label, emoji in QUESTION_BY_ID[qid]["options"]:
        if v == value:
            return f"{emoji} {label}"
    return str(value)
