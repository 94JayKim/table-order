"""AI 문자 후보를 만든다 (admin/marketing_ai.py 의 화면용 로직을 서버로 옮긴 것).

흐름: 매장 데이터 요약(수신 가능 회원 수·추천 가중치 높은 메뉴·인기 메뉴) → 키워드 조합 고르기 → 문구 만들기.
문구는 제미나이(GEMINI_API_KEY)로 만들고, 키가 없거나 호출이 실패하면 템플릿으로 대신한다(source 로 구분).
"""

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from app.core.settings import Settings
from app.services.external_info import ExternalInfoService
from app.services.grades import GRADES, grade_of
from app.services.sms import SmsService

# 키워드마다 문자를 받을 등급. 발송 API 가 '등급'으로 수신자를 정하므로 키워드도 등급으로 푼다.
# 복합 키워드는 등급의 교집합이고, 비는 조합은 만들지 않는다.
KEYWORD_GRADES = {
    "날씨": ["신규", "재방문", "단골", "휴면"],
    "행사": ["신규", "재방문", "단골", "휴면"],
    "가중치": ["신규", "재방문", "단골"],  # 추천 가중치가 높은 메뉴를 알릴 대상: 최근 온 손님
    "주문": ["신규", "재방문", "단골"],    # 최근 주문한 손님(휴면 제외)
    "휴면": ["휴면"],
    "단골": ["단골"],
}
# 화면에 먼저 보여 줄 키워드 조합 순서. 수신할 회원이 있는 조합만 앞에서부터 n개 쓴다.
CANDIDATE_ORDER = [("휴면",), ("단골",), ("주문", "단골"), ("날씨", "주문"), ("행사",), ("가중치", "주문"), ("날씨", "행사"), ("주문",)]
DEFAULT_WEATHER = "쌀쌀한 날씨"
DEFAULT_EVENT = "이번 주 특별 이벤트"
MENU_SEED = Path(__file__).resolve().parent.parent / "seed" / "menu.json"  # 메뉴 저장소가 비어 있을 때 쓰는 기본 메뉴
PROMPT = (
    "당신은 호프집 사장님을 돕는 문자 카피라이터입니다. 아래 키워드와 매장 정보로 손님에게 보낼 문자 본문 한 개만 쓰세요. "
    "구체적으로 쓰세요: 행사가 주어지면 행사명을 그대로(따옴표 안의 이름) 말하고 장소·기간도 한 가지 이상 넣으세요. "
    "날씨가 주어지면 날씨·기온을 구체적으로 말하고, 메뉴는 '인기 메뉴' 같은 두루뭉술한 말 대신 "
    "주어진 메뉴 이름(괄호 앞부분)과 그 특징 한 가지를 말하세요. "
    "주어진 정보에 없는 메뉴·행사·할인은 지어내지 마세요. "
    "한국어 존댓말, 친근한 톤, 100자 이내, 이모지 없이. (광고) 표기와 수신거부 안내는 시스템이 붙이니 쓰지 마세요. "
    "설명 없이 문구만 출력하세요.")


def keyword_grades(keywords) -> list[str]:
    """키워드들의 수신 등급 교집합 (GRADES 순서 유지). 비면 []."""
    common = set.intersection(*(set(KEYWORD_GRADES[k]) for k in keywords)) if keywords else set()
    return [g for g in GRADES if g in common]


class SmsCandidateService:
    def __init__(self, settings: Settings, sms: SmsService, shop, external: ExternalInfoService):
        self.s, self.sms, self.shop, self.external = settings, sms, shop, external

    # ---- 매장 데이터 요약 ----
    def summary(self) -> dict:
        """문구에 쓸 사실만 모은다: 등급별 수신 가능 회원 수, 추천 가중치 높은 메뉴, 인기 메뉴."""
        today = self.sms.clock().date()
        rule = {"repeat": self.s.grade_repeat_visits, "regular": self.s.grade_regular_visits,
                "dormant": self.s.grade_dormant_days}
        pool = Counter(grade_of(m, today, **rule) for m in self.sms.targets(GRADES))
        try:  # 메뉴 저장소가 아직 뼈대(NotImplementedError)면 기본 메뉴 파일(seed/menu.json)을 쓴다
            menus = self.shop.menus()
        except NotImplementedError:
            menus = json.loads(MENU_SEED.read_text(encoding="utf-8"))
        menus = [m for m in menus if not m.get("soldout")]
        # 추천 가중치가 높은 순(같으면 BEST 태그 먼저)으로 3개: 문구에 이름·가격·설명을 구체적으로 쓰기 위해 통째로 둔다
        best = sorted(menus, key=lambda m: (m.get("weight", 0), "BEST" in m.get("tags", [])), reverse=True)[:3]
        high_weight = [{"name": m["name"], "price": m.get("price"), "desc": m.get("desc", "")} for m in best]
        try:
            sold = Counter()
            for order in self.shop.orders():
                for line in order["lines"]:
                    sold[line["name"]] += line["qty"]
            top_items = [name for name, _ in sold.most_common(3)]
        except NotImplementedError:
            top_items = []
        return {"pool": dict(pool), "high_weight": high_weight, "top_items": top_items}

    # ---- 문구 만들기 ----
    def _facts(self, summary: dict, info: dict) -> dict:
        weight_menu = self._short_name(summary["high_weight"][0]["name"]) if summary["high_weight"] else "인기 메뉴"
        detail = "; ".join(f"{m['name']} {m['price']:,}원 - {m['desc']}" if m["price"] else m["name"]
                           for m in summary["high_weight"])
        return {"weight_detail": detail or weight_menu, "weather": info["weather_text"].strip() or DEFAULT_WEATHER,
                "event": info["event_text"].strip() or DEFAULT_EVENT,
                "weight_menu": weight_menu, "top_menu": (summary["top_items"] or [weight_menu])[0]}

    @staticmethod
    def _short_name(name: str) -> str:
        """메뉴 이름에서 괄호 설명을 뺀다: "역전 옛날통닭 (한 마리·후라이드)" → "역전 옛날통닭"."""
        return name.split("(")[0].strip() or name

    def template(self, keywords, f: dict) -> str:
        """AI 를 못 쓸 때의 문구: 키워드마다 한 문장을 이어 붙인다."""
        parts = {
            "날씨": f"{f['weather']}엔 따끈한 안주에 한잔 어때요?",
            "행사": f"{f['event']} 소식, 구경하시고 한잔 어때요?",
            "가중치": f"요즘 추천 1순위 ‘{f['weight_menu']}’ 드셔보세요.",
            "주문": f"지난 주문 감사해요. ‘{f['top_menu']}’ 또 드시러 오세요.",
            "휴면": "오랜만이에요! 이번 주 방문하시면 안주 10% 할인해 드려요.",
            "단골": "항상 찾아주셔서 감사해요. 방문 시 음료 1잔을 서비스로 드려요.",
        }
        return " ".join(parts[k] for k in keywords)

    def _ask_gemini(self, keywords, f: dict) -> str:
        """제미나이에 문구 한 개를 요청한다. 실패하면 예외."""
        user = (f"키워드: {', '.join(keywords)}\n오늘 날씨: {f['weather']}\n주변 행사: {f['event']}\n"
                f"추천 메뉴(이름 가격 - 특징): {f['weight_detail']}\n실제 많이 팔린 메뉴: {f['top_menu']}")
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent",
            timeout=15, headers={"x-goog-api-key": self.s.gemini_api_key},
            json={"systemInstruction": {"parts": [{"text": PROMPT}]}, "contents": [{"parts": [{"text": user}]}]})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def generate(self, keywords, f: dict) -> tuple[str, str]:
        """(문구, 출처). 출처는 'ai' 또는 'template'. 키가 없거나 호출이 실패하면 템플릿."""
        if self.s.gemini_api_key:
            try:
                text = self._ask_gemini(keywords, f)
                if text:
                    return text, "ai"
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                pass
        return self.template(keywords, f), "template"

    # ---- 후보 목록 ----
    def candidates(self, n: int = 5) -> list[dict]:
        """후보 최대 n개: [{keywords, grades, body, source}]. 수신 가능 회원이 없는 등급 조합은 뺀다."""
        summary, info = self.summary(), self.external.today()
        f = self._facts(summary, info)
        picks = [kw for kw in CANDIDATE_ORDER if any(summary["pool"].get(g, 0) for g in keyword_grades(kw))][:n]

        def make(kw):
            body, source = self.generate(kw, f)
            return {"keywords": list(kw), "grades": keyword_grades(kw), "body": body, "source": source}
        if not picks:
            return []
        with ThreadPoolExecutor(max_workers=len(picks)) as ex:  # 후보를 동시에 만들어 AI 호출 시간을 줄인다
            return list(ex.map(make, picks))
