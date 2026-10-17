"""오늘의 외부 정보(날씨·주변 행사) 문구를 만든다. 결과는 DB에 하루 한 번만 저장해 재사용한다.

- 날씨: Open-Meteo (인증키 없는 무료 API). 매장 좌표의 현재 날씨를 "맑은 18도 날씨"처럼 한 줄로 만든다.
- 행사: 서울 열린데이터광장 '서울시 문화행사 정보'(SEOUL_OPENAPI_KEY 필요). 매장이 있는 자치구에서 오늘 열리는 행사만 쓴다.
외부 호출이 실패해도 예외를 밖으로 내보내지 않고 빈 문자열을 돌려준다(문자 후보 생성이 멈추지 않게).
"""

from datetime import datetime

import httpx

from app.core.settings import Settings
from app.services.grades import KST
from app.stores.external_context import ExternalContextStore

# Open-Meteo 날씨 코드 → "맑은" 같은 꾸밈말. 코드표에 없으면 "날씨"만 쓴다.
WEATHER_WORDS = {0: "맑은", 1: "대체로 맑은", 2: "구름 많은", 3: "흐린", 45: "안개 낀", 48: "안개 낀",
                 51: "이슬비 오는", 53: "이슬비 오는", 55: "이슬비 오는", 61: "비 오는", 63: "비 오는", 65: "비 오는",
                 66: "비 오는", 67: "비 오는", 71: "눈 오는", 73: "눈 오는", 75: "눈 오는", 77: "눈 오는",
                 80: "소나기 오는", 81: "소나기 오는", 82: "소나기 오는", 85: "눈 오는", 86: "눈 오는",
                 95: "천둥 치는", 96: "천둥 치는", 99: "천둥 치는"}
EVENT_URL = "http://openapi.seoul.go.kr:8088/{key}/json/culturalEventInfo/1/200/%20/%20/{day}"


class ExternalInfoService:
    def __init__(self, settings: Settings, store: ExternalContextStore, clock=None):
        self.s, self.store = settings, store
        self.clock = clock or (lambda: datetime.now(KST))

    def today(self) -> dict:
        """오늘(KST) 날씨·행사 문구. 저장된 게 있으면 그대로, 없으면 외부 API로 채워 저장한다."""
        day = self.clock().strftime("%Y-%m-%d")
        saved = self.store.get(day)
        if saved and (saved["weather_text"] or saved["event_text"]):
            return {"day": day, "weather_text": saved["weather_text"], "event_text": saved["event_text"]}
        weather, event = self.fetch_weather(), self.fetch_events(day)
        if weather or event:  # 둘 다 실패(빈 값)면 저장하지 않아 다음 호출 때 다시 시도한다
            self.store.save(day, weather, event)
        return {"day": day, "weather_text": weather, "event_text": event}

    def fetch_weather(self) -> str:
        """매장 위치의 현재 날씨 한 줄. 실패하면 ''."""
        try:
            r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=5, params={
                "latitude": self.s.store_lat, "longitude": self.s.store_lon,
                "current": "temperature_2m,weather_code", "timezone": "Asia/Seoul"})
            r.raise_for_status()
            cur = r.json()["current"]
            word = WEATHER_WORDS.get(int(cur["weather_code"]), "")
            return f"{word} {round(cur['temperature_2m'])}도 날씨".strip()
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return ""

    def fetch_events(self, day: str) -> str:
        """매장 자치구에서 오늘 열리는 문화행사 최대 2개를 한 줄로. 키가 없거나 실패하면 ''."""
        if not self.s.seoul_openapi_key:
            return ""
        try:
            r = httpx.get(EVENT_URL.format(key=self.s.seoul_openapi_key, day=day), timeout=8)
            r.raise_for_status()
            rows = r.json()["culturalEventInfo"]["row"]
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return ""
        # 요청 날짜 필터를 믿지 않고 한 번 더 거른다: 우리 자치구 + 오늘이 시작일~종료일 사이
        titles = [row["TITLE"].strip() for row in rows
                  if row.get("GUNAME") == self.s.store_gu
                  and str(row.get("STRTDATE", ""))[:10] <= day <= str(row.get("END_DATE", ""))[:10]]
        return f"{self.s.store_gu} '{', '.join(titles[:2])}' 행사 진행 중" if titles else ""
