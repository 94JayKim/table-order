"""대시보드 화면.
"""

import streamlit as st

from admin.ui.widgets import bars, kpi, kpi_row, page_head, panel, sec_title
from dashboard_stats import customer_care, menu_alerts, summarize

ss = st.session_state


def render_sales_insights(repo):
    """매출·객단가·회전율 등 사장님용 추가 지표 (최근 30일, 가장 최근 주문일 기준)."""
    x = summarize(repo.orders(), repo.members(ss["grade_rule"]))
    sec_title("매출 분석", f"최근 {x.get('days', 0)}일 기준" if not x["empty"] else "")
    if x["empty"]:
        st.html('<div class="empty">아직 주문이 없어요.</div>')
        return
    kpi_row(
        kpi("최근 매출", f"{x['revenue']:,}", "원", sub=f"하루 평균 {x['daily_revenue']:,}원", accent=True),
        kpi("평균 객단가", f"{x['avg_ticket']:,}", "원", sub=f"주문 {x['orders']:,}건 기준"),
        kpi("테이블 회전율", x["turnover_avg"], "회/일", sub=f"테이블 {x['tables']}개 · 마지막 영업일 {x['turnover_today']}회"),
        kpi("재방문 고객 비율", f"{x['returning_share']:.0%}" if x["returning_share"] is not None else "-",
            sub="주문 고객 중 재방문·단골"),
    )
    l, r = st.columns(2, gap="medium")
    l.html(panel("시간대별 매출", f"가장 바쁜 시간은 {x['peak_hour']}", bars(x["by_hour"], "원")))
    r.html(panel("요일별 매출", f"매출이 가장 높은 요일은 {x['peak_weekday']}요일", bars(x["by_weekday"], "원")))
    l, r = st.columns(2, gap="medium")
    l.html(panel("고객 등급별 주문 고객", "최근 주문한 고객 수", bars(x["customer_grades"], "명")))
    r.html(panel("주문이 많은 테이블 TOP 5", "주문 건수 기준", bars(x["top_tables"], "건", ranked=True)))
    if x["ai_avg_ticket"] is not None and x["plain_avg_ticket"] is not None:
        kpi_row(
            kpi("AI 추천 주문 객단가", f"{x['ai_avg_ticket']:,}", "원", sub=f"전체 주문의 {x['ai_share']:.0%}"),
            kpi("일반 주문 객단가", f"{x['plain_avg_ticket']:,}", "원"),
        )
    render_trend_insights(x)


def delta_text(change, base):
    """증감률을 '▲ 12% (지난주 대비)' 형태로 (비교 대상이 없으면 안내 문구)."""
    if change is None:
        return f"{base} 데이터가 없어요"
    return f"{'▲' if change >= 0 else '▼'} {abs(change):.0%} ({base} 대비)"


def render_trend_insights(x):
    """매출 추이·회원 비중·주문 금액대·단골 고객: 장사가 좋아지는지, 누가 매출을 만드는지 보는 지표."""
    sec_title("매출 추이 · 고객 기여", f"마지막 영업일 {x['last_day']} 기준")
    member_sub = (f"회원 {x['member_avg_ticket']:,}원 · 비회원 {x['guest_avg_ticket']:,}원"
                  if x["member_avg_ticket"] and x["guest_avg_ticket"] else "회원 주문 비중")
    kpi_row(
        kpi("최근 7일 매출", f"{x['week_revenue']:,}", "원", sub=delta_text(x["week_change"], "지난 7일"), accent=True),
        kpi("마지막 영업일 매출", f"{x['last_day_revenue']:,}", "원", sub=delta_text(x["last_day_change"], "지난주 같은 요일")),
        kpi("회원 주문 비중", f"{x['member_order_share']:.0%}", sub=member_sub),
        kpi("상위 5명 매출 비중", f"{x['top_customer_share']:.0%}" if x["top_customer_share"] is not None else "-",
            sub="회원 매출 중 단골 상위 5명"),
    )
    l, r = st.columns([3, 2], gap="medium")
    l.html(panel("일별 매출 (최근 14일)", "하루 매출 흐름", bars(x["by_day"], "원")))
    r.html(panel("주문 금액대 분포", "한 번에 얼마씩 주문하는지", bars(x["ticket_bands"], "건")))
    top = {f"{c['name']} · {c['orders']}회": c["amount"] for c in x["top_customers"]}
    st.html(panel("단골 고객 TOP 5", "최근 30일 누적 결제금액 · 문자 혜택을 챙겨 드리면 좋아요",
                  bars(top, "원", ranked=True, empty="회원 주문이 아직 없어요.")))


def render_operations(repo, s):
    """고객 관리(휴면·수신 동의)와 메뉴 운영(품절) 알림."""
    sec_title("고객 관리 · 운영 알림")
    care = customer_care(repo.members(ss["grade_rule"]))
    alerts = menu_alerts(repo.menus(), s["popular_menus"])
    if care["total"]:
        kpi_row(
            kpi("전체 회원", care["total"], "명", sub=f"수신거부 {care['opted_out']}명"),
            kpi("휴면 고객", care["dormant"], "명", sub=f"전체의 {care['dormant'] / care['total']:.0%} · 마케팅 탭에서 되찾기 문자를 보내 보세요"),
            kpi("문자 수신 가능", care["consent"], "명", sub=f"전체의 {care['consent'] / care['total']:.0%}가 마케팅 수신에 동의"),
        )
    names = ", ".join(alerts["sold_out"][:4]) + (f" 외 {len(alerts['sold_out']) - 4}개" if len(alerts["sold_out"]) > 4 else "")
    kpi_row(
        kpi("품절 메뉴", len(alerts["sold_out"]), "개", sub=names or "모든 메뉴를 판매 중이에요"),
        kpi("품절된 인기 메뉴", len(alerts["popular_sold_out"]), "개",
            sub=", ".join(alerts["popular_sold_out"]) or "인기 TOP 10 메뉴는 모두 판매 중이에요"),
    )


def page_dashboard(repo):
    s = repo.stats(ss["grade_rule"])
    ai = s["ai"]
    page_head("대시보드", "오늘 매장 현황을 한눈에 확인하세요")
    kpi_row(
        kpi("오늘 주문", s["today_orders"], "건", accent=True),
        kpi("평균 주문금액", f"{s['avg_order_amount']:,}" if s["today_orders"] else "-", "원" if s["today_orders"] else ""),
        kpi("오늘 신규 고객", s["new_customers"], "명"),
        kpi("오늘 재방문 고객", s["returning_customers"], "명"),
    )
    render_sales_insights(repo)
    sec_title("고객 분석")
    l, r = st.columns(2, gap="medium")
    l.html(panel("고객 연령대", "출생연도를 입력한 회원만 집계해요", bars(s["age_groups"], "명")))
    r.html(panel("고객 성별", "회원 정보 기준", bars(s["genders"], "명")))
    sec_title("메뉴 · AI 추천")
    l, r = st.columns([3, 2], gap="medium")
    l.html(panel("인기 메뉴 TOP 10", "주문 수량 기준",
                 bars({m["name"]: m["qty"] for m in s["popular_menus"]}, "개", ranked=True, empty="아직 주문이 없어요.")))
    with r:
        kpi_row(kpi("AI 추천 적중률", f"{ai['hit_rate']:.0%}" if ai["hit_rate"] is not None else "-",
                    sub="임시 기준 · 정확한 계산 기준은 추가 정의가 필요해요"),
                kpi("추천 노출", ai["recommendations"], "회", sub=f"조합이 포함된 주문 {ai['ai_orders']}건"))
        st.caption(f"적중 기준(임시): {ai['definition']}")
    render_operations(repo, s)
