"""주문 이력 필터 (화면 코드와 분리해서 단독으로 테스트할 수 있게 둔다)."""
from __future__ import annotations

from datetime import date

import pandas as pd

AI_ALL, AI_USED, AI_NOT_USED = "전체", "AI 추천 사용", "사용 안 함"
AI_CHOICES = [AI_ALL, AI_USED, AI_NOT_USED]


def filter_orders(df: pd.DataFrame, *, start: date | None = None, end: date | None = None, tables=(),
                  keyword: str = "", ai: str = AI_ALL, min_amount: int | None = None,
                  max_amount: int | None = None) -> pd.DataFrame:
    """조건을 모두 만족하는 주문만 남긴다. 비어 있는 조건은 무시한다.

    keyword 는 닉네임·주문 내역(메뉴 이름)·주문번호에서 대소문자 구분 없이 찾는다.
    """
    out = df
    day = out["주문 시각"].dt.date
    if start:
        out = out[day >= start]
        day = out["주문 시각"].dt.date
    if end:
        out = out[day <= end]
    if tables:
        out = out[out["테이블"].isin(list(tables))]
    kw = (keyword or "").strip()
    if kw:
        haystack = out["닉네임"].astype(str) + " " + out["주문 내역"].astype(str) + " " + out["order_id"].astype(str)
        out = out[haystack.str.contains(kw, case=False, regex=False)]
    if ai == AI_USED:
        out = out[out["AI 추천 사용"]]
    elif ai == AI_NOT_USED:
        out = out[~out["AI 추천 사용"]]
    if min_amount:
        out = out[out["금액"] >= min_amount]
    if max_amount:
        out = out[out["금액"] <= max_amount]
    return out
