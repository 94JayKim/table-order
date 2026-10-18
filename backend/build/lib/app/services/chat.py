"""관리자 AI 챗봇: DB 데이터를 문장으로 요약해 프롬프트에 붙이고 제미나이에 질문한다 (RAG·MCP 없음)."""

from collections import Counter
from datetime import date, datetime, timedelta

import httpx

from app.core.settings import Settings
from app.services import stats as stats_service
from app.services.grades import KST

GREETING = "안녕하세요 사장님! 매장 데이터를 보고 궁금한 점에 답해 드릴게요. 예) 저번주 총 매출 알려줘"
NO_KEY_REPLY = "AI 챗봇을 쓰려면 서버에 GEMINI_API_KEY 설정이 필요해요. 관리자에게 설정을 요청해 주세요."
HISTORY_LIMIT = 20  # 제미나이에 다시 보내는 이전 대화 개수 (무료 한도·토큰을 아끼려고 최근 것만)

PROMPT = (
    "당신은 호프집 사장님을 돕는 매장 데이터 도우미입니다. 한국어로 짧고 친절하게 답하세요.\n"
    "반드시 아래 '매장 데이터'에 있는 숫자와 사실만 근거로 답하세요. 데이터에 없거나 '집계 전'인 내용은 "
    "추측하지 말고 '아직 알 수 없어요'라고 답하세요. 금액은 원 단위로 쉼표를 붙여 말하세요.\n"
    "질문의 '오늘·어제·이번 주·저번 주(지난주)·이번 달·지난달'은 데이터의 같은 이름 항목을 보세요."
)


class ChatUnavailable(Exception):
    """제미나이 호출이 실패했다(한도 초과·네트워크 오류 등). 라우터가 502 로 바꾼다."""


class ChatService:
    def __init__(self, settings: Settings, stats_store, members):
        self.s = settings
        self.stats_store = stats_store
        self.members = members

    # ---- 매장 데이터 요약 ----
    @staticmethod
    def _period(orders: list[dict], start: date, end: date) -> str:
        """start~end(양 끝 포함) 기간의 매출·주문 건수를 한 줄 문장으로 만든다."""
        picked = [o for o in orders if start <= o["day"] <= end]
        if not picked:
            return "주문 없음(0원)"
        return f"매출 {sum(o['total'] for o in picked):,}원, 주문 {len(picked)}건"

    def summary(self, today: date) -> str:
        """기간별 매출·인기 메뉴·회원 수를 프롬프트에 넣을 문장으로 만든다. 합계는 항상 서버가 계산한다."""
        # 시각 문자열을 한국 날짜로 바꿔 두면 기간 비교가 쉽다.
        orders = [{**o, "day": stats_service.order_date(o["ts"])} for o in self.stats_store.sales_orders()]
        this_monday = today - timedelta(days=today.weekday())  # 이번 주 월요일
        last_monday = this_monday - timedelta(days=7)
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        lines = [
            f"오늘은 {today:%Y-%m-%d}({stats_service.WEEKDAYS[today.weekday()]}요일)입니다.",
            f"- 오늘: {self._period(orders, today, today)}",
            f"- 어제: {self._period(orders, today - timedelta(days=1), today - timedelta(days=1))}",
            f"- 이번 주({this_monday:%m/%d}~오늘): {self._period(orders, this_monday, today)}",
            f"- 저번 주(지난주, {last_monday:%m/%d}~{this_monday - timedelta(days=1):%m/%d}): "
            f"{self._period(orders, last_monday, this_monday - timedelta(days=1))}",
            f"- 이번 달: {self._period(orders, month_start, today)}",
            f"- 지난달: {self._period(orders, last_month_end.replace(day=1), last_month_end)}",
            f"- 전체 누적: 매출 {sum(o['total'] for o in orders):,}원, 주문 {len(orders)}건",
        ]
        sold = Counter()
        for row in self.stats_store.menu_sales():
            sold[row["name"]] += row["qty"]
        top = ", ".join(f"{name} {qty}개" for name, qty in sold.most_common(5))
        lines.append(f"- 인기 메뉴(누적 판매 수량 상위 5): {top or '판매 기록 없음'}")
        lines.append(f"- 전체 회원 수: {len(self.members.all())}명")
        return "\n".join(lines)

    # ---- 제미나이 ----
    def _ask_gemini(self, system: str, history: list[dict], question: str) -> str:
        """이전 대화 + 새 질문을 보내 답변 텍스트를 받는다. 실패하면 예외."""
        recent = history[-HISTORY_LIMIT:]
        while recent and recent[0]["role"] != "user":  # 제미나이는 user 메시지로 시작해야 하므로 첫 인사 같은 앞쪽 assistant 는 뺀다
            recent = recent[1:]
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                    for m in recent]
        contents.append({"role": "user", "parts": [{"text": question}]})
        r = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}:generateContent",
            timeout=15, headers={"x-goog-api-key": self.s.gemini_api_key},
            json={"systemInstruction": {"parts": [{"text": system}]}, "contents": contents})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    def answer(self, history: list[dict], question: str, today: date | None = None) -> str:
        """질문에 대한 답변. 키가 없으면 안내 문구를 돌려주고, 호출이 실패하면 ChatUnavailable."""
        if not self.s.gemini_api_key:
            return NO_KEY_REPLY
        today = today or datetime.now(KST).date()
        system = f"{PROMPT}\n\n[매장 데이터]\n{self.summary(today)}"
        try:
            text = self._ask_gemini(system, history, question)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # 무료 한도 초과: 재시도하지 않고 안내만 한다
                raise ChatUnavailable("AI 호출 한도를 넘었어요. 잠시 후 다시 시도해 주세요.") from e
            raise ChatUnavailable("AI 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.") from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise ChatUnavailable("AI 답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.") from e
        if not text:
            raise ChatUnavailable("AI 답변이 비어 있어요. 다시 질문해 주세요.")
        return text
