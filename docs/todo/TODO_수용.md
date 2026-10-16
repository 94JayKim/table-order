# 수용 TODO · 관리자 대시보드 · 고객 등급(수신거부 포함)

## 시작 전 공통 규칙

| 항목 | 내용 |
|---|---|
| 경로 표기 | `B/`=`backend/app/` · `A/`=`admin/` · `U/`=`user/` · `T/`=루트 `tests/` · `BT/`=`backend/tests/` |
| 브랜치 | 본 리포를 포크 → 내 포크 `main`에서 계속 개발 → PR은 본 리포 `dev`로만(한 PR에 TODO 항목 하나). 시작 전 `git fetch upstream && git pull --rebase upstream dev`. 커밋·PR 메시지 규칙은 `AGENTS.md` |
| 더미 주석처리 (더미 기능만, 구현보다 먼저) | ① 라우터의 `return dummy.xxx(...)` 줄을 `#`으로 주석처리하고 그 아래에 `raise NotImplementedError`를 둔다 ② `B/dummy/` 안의 본인 담당 `*_data.py`(예: `menu_data.py`)에서 해당 함수와 그 파일의 `ENDPOINTS` 줄을 **같이** 주석처리한다(한쪽만 하면 `test_every_listed_dummy_function_exists`가 실패. `dummy/__init__.py`는 고치지 않는다) ③ 구현·테스트가 끝나면 주석처리해 둔 줄을 지운다 |
| 건드리지 않는 것 | 화면쪽 더미(`U/menu_data.py`, `A/admin_dummy_data.py`)는 서버 없이도 화면이 뜨게 하는 대체 데이터라 지우지 않는다 |
| SQL 위치 | SQL은 `B/stores/`에서만 쓴다. 라우터에는 쓰지 않는다. 테이블 정의 기준은 `docs/db/fbgrowth_schema.sql` |
| 테스트 | 서버 `cd backend && uv run pytest -q` · 화면+통합 `python -m pytest tests -q`. 둘 다 실패 없이 통과해야 PR을 보낸다. 테스트를 skip·삭제해서 통과시키지 않는다(더미 교체 시 `skip` 제거만 허용) |
| 새 테스트 | 공용 파일을 건드리지 말고 본인 이름의 새 파일(예: `BT/test_roulette.py`)에 만든다. `BT/test_dummy_get.py`에서는 본인 기능 줄만 뺀다 |
| 코드 작성 | 수정 파일은 최소로, 기존 코드는 최대한 유지, 새 코드에는 초급 개발자도 읽을 수 있는 한국어 주석(무엇을·왜)을 단다 |
| PR 본문 | 변경 내용 · 테스트 방법 · 테스트 결과 · 미해결 문제(없으면 "없음") |

## 진행 순서

| 순서 | 할 일 | API | 상태 |
|---|---|---|---|
| 0 | 0. 개발 흐름 확인 (테스트 버튼) | `POST /api/dev/db-test` (개발 전용) | 확인 전 |
| 1 | 1. 고객 등급 · 수신거부 점검 | `GET /api/admin/customers`, `…/customers/grades`, `…/grades/rules`, `POST …/customers/{id}/opt-out` | 1-1 기존 구현 / 1-2 구현·자동 테스트 완료 |
| 2 | 2. 대시보드 기본 통계 | `GET /admin/api/stats/sales`, `stats/menus/ranking`, `stats/customers`, `stats/ai-recommendations` | 구현·기능 테스트 완료 (전체 화면 테스트의 기존 룰렛 오류 별도) |
| 3 | 3. 대시보드 추가 통계 | `stats/sales/hourly·trends·weekday·tickets`, `stats/tables` | 구현·기능 테스트 완료 (전체 화면 테스트의 기존 룰렛 오류 별도) |
| 4 | 4. 운영 알림 | `GET /api/admin/alerts` | 미구현 |

**다른 팀원과 겹치는 지점**

| 파일 | 누구와 | 규칙 |
|---|---|---|
| `B/stores/shop_orders.py` | 재현(주문 저장) | 수정하지 않는다. 통계용 읽기 SQL은 `B/stores/stats.py`(신규)에 만든다 |
| `B/services/stats.py` | 성호(챗봇이 "오늘 매출"을 물을 때 호출) | 수용만 수정. 함수 이름이 바뀌면 성호에게 알린다 |
| `B/dummy/` | 재현·서준·석원 | `stats_data.py`(`dashboard_stats`와 `"GET /admin/api/stats"` 줄)만 다룬다. `members()`·`orders()` 더미는 재현의 주문 이력이 쓰므로 재현과 순서를 맞춘다 |
| `A/admin_repository.py` | 모두 | `# ---- 고객 / 주문 / 통계 ----` 구역 안에서만 수정 |

**먼저 알아둘 점**: 통계는 주문 데이터가 있어야 확인할 수 있다. 재현이 주문 저장(`POST /orders`)을 끝내기 전에는 테스트에서 `orders`/`order_items`에 직접 INSERT 해 둔 값(픽스처)으로 확인한다.

---

## 0. 개발 흐름 확인 (테스트 버튼) — 가장 먼저

본격적으로 구현하기 전에, 내 PC에서 **포크 → DB 쓰기·읽기 → 커밋·푸시 → PR** 흐름이 막힘없이 되는지 한 번 확인한다. AI에게 아래 내용을 그대로 시키면 된다.

- [ ] **0-1. 포크·최신화**: 본 리포를 포크해 내려받고, `upstream`을 등록한 뒤 `git pull --rebase upstream dev`로 내 `main`을 최신 `dev`에 맞춘다.
- [ ] **0-2. test 테이블 확인**: Supabase `table-order`에는 `test` 테이블(`id`, `value`, `created_at`, RLS 켜짐)을 **이미 만들어 두었다**. 없다면(다른 프로젝트·새 DB) `docs/db/fbgrowth_test_table.sql`을 SQL Editor에서 실행한다.
- [ ] **0-3. 테스트 버튼 만들기** (내 포크에서만, 본 리포에는 올리지 않는다. `DEV_TEST_BUTTON=1`일 때만 보이는 **개발 전용** 버튼):
  - 위치: **손님 시작 화면(룰렛이 있는 화면)**(`U/views/splash.py`)의 "📱 로그인" 버튼(`key="login_open"`) 옆. 화면 코드는 `api`를 직접 부르지 말고 `U/user_repository.py`를 통해서만 서버를 부른다.
  - 서버: `POST /api/dev/db-test`(`B/routers/dev.py` 신규, SQL은 `B/stores/`의 신규 저장소에). `test` 테이블에 임의 값을 INSERT → 같은 행을 다시 SELECT → 값이 같으면 `{"result": 1}`, 아니면 `{"result": 0}`. 행은 지우지 않고 `test` 테이블에 남겨 둔다(Supabase에서 값이 실제로 들어갔는지 눈으로 볼 수 있다).
  - 서버 `.env`에 `DEV_TEST_BUTTON=true`일 때만 이 경로를 열고, 꺼져 있으면 404. 화면 쪽은 환경변수 `DEV_TEST_BUTTON=1`일 때만 버튼을 보인다. `.env.example`에도 적는다.
  - 화면에는 결과 `1`(정상) 또는 실패 이유를 표시한다.
- [ ] **0-4. 테스트**: `cd backend && uv run pytest -q`와 `python -m pytest tests -q`가 통과하는지 확인한다.
- [ ] **0-5. 버튼 확인**: 서버와 손님 화면(`streamlit run user/app.py`)을 `DEV_TEST_BUTTON`을 켠 채 실행하고, 버튼을 눌러 `1`이 나오는지 본다.
- [ ] **0-6. 커밋·푸시·PR**: `AGENTS.md`의 커밋 메시지 규칙대로 커밋하고 내 포크 `main`에 푸시한 뒤, **본 리포 `dev`로 PR**을 보낸다(제목 `종류: 한글 요약`, 본문: 변경 내용·테스트 방법·테스트 결과·미해결 문제).
- [ ] **0-7. 마무리**: 이 PR은 흐름 확인용이므로 **머지하지 않고 PR만 닫는다**(버튼 코드는 `dev`에 들어가지 않는다). 확인이 끝나면 위 항목을 모두 `[x]`로 바꾸고 맨 위 진행 순서 표의 0번 상태를 "완료"로 고친다. 이 체크 변경은 첫 실제 기능 PR에 함께 넣는다.

> 이 단계에서 막히면(포크·푸시·DB 연결·PR 권한 등) 구현을 시작하지 말고 먼저 팀에 알린다. 실제 문제 기록은 `docs/TODO_충돌_오류.md`에 남긴다.

---

## 1. 고객 등급 · 수신거부 (구현 / 부분 구현)

### 1-1. `GET /api/admin/customers`, `POST /api/admin/customers/{customerId}/opt-out` (구현됨)

**목표**: 이미 동작한다(`B/routers/admin/members.py`). 고객 목록에 등급이 붙고, 쿼리(`repeat`, `regular`, `dormant`)로 등급 기준을 미리 바꿔 볼 수 있다(저장은 안 됨). 코드를 고치기보다 **다른 기능이 의존하는 계약**이므로 모양을 바꾸지 않는 것이 중요하다.

**테스트 방법**: `BT/test_shop_admin.py::test_members_grades_with_rule_preview_and_profile`(이미 통과 중), `python -m pytest tests/test_admin_data_source.py -q`. 수동: 관리자 > 고객 등급에서 기준을 바꾸면 등급 분포가 바뀐다.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 파생 값은 저장하지 않는다 | 등급은 방문 횟수·마지막 방문일에서 **계산**한다(`B/services/grades.py grade_of`). 기준이 바뀌면 전원이 바로 다시 분류된다 |
| 등급 규칙 | 휴면(마지막 방문 N일 경과) → 단골(방문 ≥ regular) → 재방문(≥ repeat) → 신규 순으로 먼저 맞는 것을 쓴다 |
| 쿼리 파라미터 미리보기 | 저장하지 않고 요청 값으로만 계산해 "이렇게 바꾸면 어떻게 될까"를 보여 준다 |

**흐름**
```
UI(고객 등급 · 기준 조절) → A/views/customers.py → repo.members(rule) (A/admin_repository.py)
 → GET /admin/api/members?repeat&regular&dormant → B/routers/admin/members.py list_members
 → B/stores/members.py all() → DB(members) → B/services/grades.py (등급·연령대 계산)
 → {rule, members:[{id, nickname, grade, age_group,...}]} → pandas 표 → UI 표 + 등급 분포
```

**상세 설명 / TODO**

- [x] 수신거부 API는 이미 구현(`member_opt_out`)이라 수정 없음. 문자 발송(성호)이 같은 `members.opted_out`을 읽으므로 컬럼 의미를 바꾸지 않는다.
- [x] 신규 엔드포인트는 같은 파일 `members.py`의 **아래쪽에 추가**만 한다(기존 함수 수정 금지).

### 1-2. `GET /admin/api/customers/grades`, `GET /admin/api/customers/grades/rules` (구현·자동 테스트 완료)

**목표**: `grades`는 등급별 고객 수 + 휴면 수, `grades/rules`는 현재 등급 기준(`repeat`, `regular`, `dormant`)을 돌려준다. 기존에는 `list_members` 응답 안의 `rule`/`grade`를 화면이 모아서 썼으며, 이제 전용 엔드포인트로 분리했다.

**실제 경로**: `docs/개발_가이드.md`의 관리자 경로 규칙(`/admin/api/...`)을 따른다. 기획서의 `/api/admin/...` 표기와 구분한다.

**테스트 방법**: 새 `BT/test_customer_grades.py` — 회원 4명(신규/재방문/단골/휴면 각 1명)을 만들고 `grades`가 `{신규:1, 재방문:1, 단골:1, 휴면:1}` / `rules`가 설정값(`GRADE_REPEAT_VISITS` 등)과 같음 / 쿼리로 기준을 바꾸면 분포가 바뀜 / 인증 없으면 401.

**중요 이론**: 집계(group by)를 SQL로 할지 파이썬으로 할지 — 회원 수가 적은 프로토타입은 `members.all()` 후 파이썬 계산이 단순하다. 기준값 우선순위는 `쿼리 > 설정(.env) > 기본값`(`B/routers/admin/common.py grade_rule`).

**흐름**
```
UI(대시보드 · 등급 카드 / 고객 등급 기준 패널) → A/views/dashboard.py · customers.py → repo (새 메서드)
 → GET /admin/api/customers/grades → B/routers/admin/members.py (새 함수)
 → B/stores/members.py all() → DB(members) → B/services/grades.py grade_of → 등급별 개수 집계
 → {신규, 재방문, 단골, 휴면, dormant_count} → UI 등급 카드
```

**상세 설명 / TODO**

- [x] `grades`, `grades/rules` 두 함수를 `members.py` 맨 아래에 추가(경로 충돌 주의: `/customers/grades`가 `/customers/{customerId}/…`보다 **먼저** 선언돼야 한다).
- [x] 새 `/admin/api/customers` 경로를 추가하고 기존 `/admin/api/members` 및 수신거부 응답을 유지한다. 목록·수신거부 별칭은 기존 함수를 그대로 사용한다.
- [x] 고객 등급 카드·기준 미리보기·대시보드 휴면 고객 수가 같은 집계 API를 사용한다. 등급 계산은 기존 `grade_of()`를 재사용한다.

**2026-10-16 구현·검증 기록**

- `services/grades.py`의 `grade_counts()`가 회원 방문 기록을 읽어 인원을 집계한다. 새 테이블이나 등급 저장 컬럼은 추가하지 않았다.
- 기준 조회 API의 서버 설정을 화면 초기값·기본값 복원에 사용한다. 미리보기는 요청 쿼리로만 적용하며 설정·방문 기록을 저장하지 않는다.
- 등급 분류 기준 화면에 실시간 고객 수 카드를 추가했다. 예시 회원 4명에서 단골 기준을 5회 → 10회로 바꾸면 재방문 1명 → 2명, 단골 1명 → 0명으로 바뀌는 것을 확인했다.
- 새 서버 테스트 `BT/test_customer_grades.py`: 16개 통과(등급별 집계, 빈 DB, 설정·쿼리 우선순위, 미리보기 미저장, 잘못된 기준 422, 인증 401, 기존 경로 호환, KST 경계).
- 새 화면 테스트 `T/test_sooyong_customer_grades.py`: 3개 통과(서버·더미 응답 계약, 서버 기본값·미리보기·초기화, 빈 회원 목록).
- 전체 테스트: 서버 **77 passed, 10 skipped**, 화면·통합 **102 passed, 12 skipped**. 기존 skip은 변경하지 않았다.
- 화면·통합 테스트는 서버 가상환경 Python에 루트 가상환경 패키지 경로를 추가해 실행했다. 의존성 파일은 변경하지 않았다.
- 전후 이미지 검증은 별도 메모리 DB·로컬 서버에서 진행했다. 실제 Supabase 데이터는 변경하지 않았다.
- 실제 Supabase 조회도 추가 확인했다: 필요한 테이블 27개 존재, 회원 41명, 신규 11명·재방문 12명·단골 10명·휴면 8명. 기존 8000번 서버의 DB 점검·등급 기준·등급 집계 API가 모두 200으로 응답했다.
- API 모드 관리자 화면(18502번)을 별도로 실행하고 고객 목록 41명이 오류 없이 표시되는 것을 확인했다. 수신거부 등 실제 DB 변경 작업은 수행하지 않았다.

---

## 2. 대시보드 기본 통계 (구현·기능 테스트 완료)

### 2-1. `GET /admin/api/stats/sales`, `…/stats/menus/ranking`, `…/stats/customers`, `…/stats/ai-recommendations`

**현재 상태**: `GET /admin/api/stats`의 기본 통계 전체와 4개 세부 API를 실제 DB로 구현했다. 기존 응답 키와 화면 호출 경로를 유지한다. 매출 추이·테이블 통계는 아래 3번에서 DB로 전환했으며, 4번 운영 알림은 아직 화면 계산 경로다.

**2026-10-16 초기 작업 기록: 오늘 주문 건수만 구현 (이후 2번 전체로 확장)**

- 신규 `B/stores/stats.py`의 `StatsStore.count_orders_on()`으로 조회한다. 주문 저장 파일·DB 스키마는 변경하지 않았다.
- KST 오늘 0시 이상, 다음 날 0시 미만의 주문을 센다. 같은 회원·테이블의 반복 주문과 비회원 주문도 각각 한 건으로 집계하며 메뉴 수량은 합산하지 않는다.
- Supabase는 UTC 범위의 `COUNT(*)`로 조회한다. SQLite는 공백·T·시간대 표기가 섞인 시각을 파이썬에서 비교해 날짜 경계 오집계를 방지한다.
- 주문 내역이 비어 있어도 대시보드의 오늘 주문 0건 카드를 표시한다. 기존 더미 통계 테스트는 `BT/test_sooyong_today_orders.py`로 옮겨 다른 필드의 응답 계약까지 유지하는지 확인했다.
- 새 기능 테스트: 서버 **15 passed**, 화면 **2 passed**. KST 자정·마이크로초 경계, 빈 DB, 중복 집계 방지, 인증, 새로고침 반영을 확인했다.
- 실제 Supabase의 읽기 전용 트랜잭션에서 오늘 주문 **2건**을 확인했다. 별도의 날짜 비교와 현재 API 응답도 일치했으며 실제 주문은 추가·변경하지 않았다.
- 전체 서버 테스트: **92 passed, 10 skipped**. 전체 화면·통합 테스트: **97 passed, 12 skipped, 7 failed**. 실패 7개는 모두 `T/test_admin_events_page.py`의 룰렛 관련 테스트이며, 수정 전 원본 커밋 `69ae21c`의 별도 사본에서도 같은 7개 실패가 재현됐다. 다른 담당 영역은 수정하지 않았다.
- 당시에는 오늘 주문만 구현했으므로 2번 전체 체크박스를 완료로 표시하지 않았다. 이후 완료 기록은 아래와 같다.

**2026-10-16 2번 전체 구현·검증 기록**

- `StatsStore.orders()`가 주문·주문 줄·조합 구성 메뉴를 세 번의 읽기 쿼리로 묶는다. 추천 노출 수는 `recommendation_events`에서 조회한다. 주문 저장 담당 파일·스키마·실제 DB 기록은 변경하지 않았다.
- 오늘(KST) 주문 수·평균 결제금액(원 단위 버림), 오늘 주문한 고유 회원의 신규/재방문 수를 계산한다. 비회원은 고객 등급 인원에서 제외하고 휴면은 신규·재방문에 넣지 않는다. 회원 연령·성별 분포는 전체 회원 기준이며 미입력 정보는 제외한다.
- 인기 메뉴와 AI 지표는 전체 기록 기준이다. 조합 수량 × 구성 메뉴 수량으로 인기 메뉴 TOP10을 계산한다. AI 적중률은 AI 포함 주문 수 / 추천 노출 수이며 노출 0회면 `null`이다. 정의를 화면에 표시한다.
- 세부 응답: `sales`는 `{today_orders, avg_order_amount}`, `menus/ranking`은 `{popular_menus}`, `customers`는 `{new_customers, returning_customers, age_groups, genders}`, `ai-recommendations`는 `{recommendations, ai_orders, hit_rate, definition}`이다. 같은 계산 함수를 사용한다.
- 등급 미리보기 쿼리를 화면에서 통계 API로 전달하며 저장하지 않는다. 잘못된 기준은 422, 미인증 요청은 401이다.
- 서버 더미 함수·엔드포인트 목록을 제거했다. 기존 통계 테스트의 skip을 해제하고, 아직 더미인 주문·추천 쓰기 대신 메모리 DB 픽스처를 준비해 실제 통계 API를 검증한다.
- 서버 기능 테스트 **26 passed**. 화면 기능 테스트 3개를 포함한 지정 테스트 **11 passed, 4 skipped**. 전체 서버 **103 passed, 9 skipped**. 테스트를 새로 skip하거나 삭제하지 않았다.
- 최종 전체 화면·통합 테스트 **98 passed, 12 skipped, 7 failed**. 실패는 수정 전 원본에서도 재현된 `T/test_admin_events_page.py`의 기존 룰렛 7개뿐이다. 최초 실행의 임시 폴더 권한 오류는 권한을 확보해 재실행한 결과 해소됐다. 2번 구현은 커밋하되 전체 테스트 통과 전에는 PR을 보내지 않는다.
- 실제 Supabase 읽기 전용 검증에서 전체·세부 API 모두 200: 오늘 주문 2건, 평균 68,200원, 신규 0명·재방문 2명, 인기 메뉴 10개, 추천 65회·AI 주문 40건·적중률 약 61.5%를 확인했다.

**목표**: 오늘 주문 수·평균 주문금액·오늘 신규/재방문 고객, 연령대·성별 분포, 인기 메뉴 TOP10, AI 추천 노출 수와 적중률을 DB에서 계산한다.

**테스트 방법**

| 방법 | 확인할 것 |
|---|---|
| `BT/test_shop_admin.py::test_stats_and_ai_hit_rate`의 `skip` 해제 | 통과 |
| 새 `BT/test_stats.py` | 주문 3건 입력 → `today_orders=3`, `avg_order_amount`가 합계/건수, 어제 주문은 오늘 집계에서 제외(KST), 조합(`combo:`) 주문은 **구성 메뉴 단위**로 인기 메뉴에 셈, `hit_rate = ai_orders / recommendations`(분모 0이면 `null`) |
| `python -m pytest tests/test_dashboard_stats.py tests/test_data_source.py -q` | 화면 쪽 통계가 그대로 통과 |
| 수동 | 대시보드 숫자가 고정값(3건, 30,666원)에서 실제 값으로 바뀐다 |

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 집계 함수 | `COUNT`(건수), `SUM`(합계), `AVG`(평균), `GROUP BY`(묶어서 계산). 대부분의 통계는 이 네 가지다 |
| KST 하루 | DB 시각은 UTC. "오늘"은 KST 0시~24시를 UTC로 바꿔 비교한다 (`B/stores/coupons.py _today_start_utc` 참고) |
| 신규 vs 재방문 | 오늘 주문한 회원을 `grades.grade_of`로 분류해 신규는 신규로, 재방문+단골은 재방문으로 센다 |
| 적중률 | 분자=AI 조합이 포함된 주문 수(`orders.ai_combo`), 분모=추천 노출 수(`recommendation_events`). 정의 문장을 응답 `definition`에 함께 내려 화면에 보여 준다 |
| 0으로 나누기 | 분모가 0이면 `None`을 돌려주고 화면은 "-"로 보여 준다 |

**흐름**
```
UI(대시보드 KPI 카드) → A/views/dashboard.py → repo.stats(rule) (A/admin_repository.py)
 → GET /admin/api/stats → B/routers/admin/stats.py dashboard
 → B/stores/stats.py(신규): 오늘 주문 / 메뉴별 수량 / 추천 노출 수를 SELECT
   + B/stores/members.py all()
 → B/services/stats.py dashboard(orders, members, recommendations, today, rule): 파이썬으로 집계
 → DB(orders, order_items, order_item_components, recommendation_events, members) → 계산 결과 dict
 → UI KPI 카드 · 연령대/성별 막대 · 인기 메뉴 · AI 적중률
```

**상세 설명 / TODO**

- [x] 서버 통계 더미 호출·함수·엔드포인트 목록 제거.
- [x] `B/services/stats.py dashboard()` 구현. 기존 반환 키(`today_orders, avg_order_amount, new_customers, returning_customers, age_groups, genders, popular_menus, ai`) 유지.
- [x] `B/stores/stats.py`: 주문 목록(줄·구성 메뉴 포함), 추천 노출 수 조회. `shop_orders.py` 수정 없음.
- [x] 라우터에서 `today = datetime.now(KST).date()`, `rule = grade_rule(settings)`로 호출. 미리보기 쿼리 지원.
- [x] 4개의 세분화 경로는 같은 `dashboard()` 결과의 해당 부분만 반환. 화면은 기존 `/stats` 사용.
- [x] `BT/test_dummy_get.py::test_admin_get_dummies`의 stats 줄을 수용 통계 테스트로 대체.

---

## 3. 대시보드 추가 통계 (구현·기능 테스트 완료)

### 3-1. `stats/sales/hourly` · `stats/sales/weekday` · `stats/sales/trends` · `stats/sales/tickets` · `stats/tables`

**현재 상태**: 5개 세부 API와 화면용 묶음 조회 `GET /admin/api/stats/insights`를 구현했다. API 모드 대시보드는 실제 DB의 추가 통계를 사용하고, 더미 모드는 `A/dashboard_stats.py`의 기존 계산을 유지한다.

**목표**

| 경로 | 내용 | 참고하는 화면 함수 |
|---|---|---|
| `stats/sales/hourly` | 시간대별 매출 | `summarize`의 `by_hour` |
| `stats/sales/weekday` | 요일별 매출 | `by_weekday` |
| `stats/sales/trends` | 최근 7일 / 마지막 영업일 / 일별(14일) 매출과 증감률 | `_trend_stats` |
| `stats/sales/tickets` | 객단가·금액대 분포·AI 추천 vs 일반 객단가 | `ticket_bands`, `ai_avg_ticket` |
| `stats/tables` | 테이블 회전율·주문 많은 테이블 TOP5 | `turnover_*`, `top_tables` |

**테스트 방법**: 같은 주문 데이터로 **화면 계산(`dashboard_stats.summarize`)과 서버 계산 결과가 같다**는 테스트를 `BT/test_stats.py`에 추가한다(둘 중 하나가 틀리면 바로 드러난다). 빈 데이터면 `empty` 상태(0 또는 빈 객체)를 돌려주고 500이 나지 않는다.

**중요 이론**

| 개념 | 한 줄 설명 |
|---|---|
| 시간 단위로 묶기 | `GROUP BY` 시(hour) / 요일 / 날짜. DB마다 함수가 달라서(SQLite `strftime`, Postgres `extract`) 프로토타입에서는 파이썬으로 묶는 편이 안전하다 |
| 기준일 | 화면은 "가장 최근 주문일" 기준 최근 30일이다. 같은 규칙을 서버도 따라야 숫자가 일치한다 |
| 회전율 | 하루 주문 건수 / 전체 테이블 수(`store_info.tables`) |
| 증감률 | (이번 − 지난) / 지난. 지난 값이 0이면 `None` |
| 객단가 | 주문 1건당 평균 결제금액 = 매출 / 주문 수 |

**흐름**
```
UI(대시보드 · 시간대/요일 막대, 추이, 테이블 TOP5) → A/views/dashboard.py render_sales_insights·render_trend_insights
 → (현재) repo.orders() 전체 → A/dashboard_stats.py (pandas)
 → (변경) GET /admin/api/stats/sales/hourly 등 → B/routers/admin/stats.py → B/services/stats.py → B/stores/stats.py
 → DB(orders …) → 집계 dict → UI 막대·KPI
```

**상세 설명 / TODO**

- [x] 라우트는 `B/routers/admin/stats.py`에 추가(수용 단독 파일). 계산 함수는 `B/services/stats.py`에, SQL은 `B/stores/stats.py`에.
- [x] 화면(`A/dashboard_stats.py`)의 계산을 `sales_insights()`·`_sales_trends()`로 함수 단위 이식하고 서버 자료형에 맞게 적용했다. 화면쪽 원본은 유지한다(`DATA_SOURCE=dummy` 대체 경로).
- [x] 화면은 `A/views/dashboard.py`와 `A/admin_repository.py` 통계 호출 구역만 수정한다. 주문 목록의 더미 여부와 무관하게 DB 집계를 표시한다.
- [x] `stats/tables`의 전체 테이블 수는 `app.state.store_info.get()["tables"]`에서 읽는다.

**2026-10-16 3번 구현·검증 기록**

- `StatsStore.sales_orders()`가 주문과 회원 닉네임을 한 번의 읽기 쿼리로 가져온다. 추가 통계에 필요 없는 메뉴 줄·조합 구성은 조회하지 않는다. 주문 저장 담당 파일과 DB 스키마는 변경하지 않았다.
- 실제 API 경로는 `/admin/api/stats/sales/hourly`, `…/weekday`, `…/trends`, `…/tickets`, `/admin/api/stats/tables`다. 세부 API는 같은 계산의 필요한 항목과 `empty`를 반환한다. 화면은 `/admin/api/stats/insights`를 한 번 호출해 추가 통계 전체를 받는다.
- 최근 30일은 마지막 주문일 포함 30일, 최근 7일과 이전 7일은 겹치지 않는 기간, 일별 그래프는 최근 14일이다. 매출이 없는 날짜는 0원이다. 일평균·회전율의 일수는 기존 화면과 동일하게 주문이 발생한 날짜 수다.
- 시각을 KST로 통일하고 UTC·KST·시간대 없는 SQLite 문자열을 모두 처리한다. 비교 매출 0원일 때 증감률, 해당 주문이 없는 집단의 객단가는 `null`이다. 빈 주문 목록은 모든 추가 API에서 `{"empty": true}`로 반환한다.
- 자체 검토에서 발견한 기존 표시 오류를 수정했다. `오늘 매출`은 실제 KST 오늘 매출, `마지막 영업일 매출`은 마지막 주문일 매출이다. 오늘 주문이 없으면 오늘 매출은 0원이며, 고객 매출·테이블 순위의 제목도 실제 집계일인 마지막 영업일로 명시한다. 화면 상단에 기준일 안내를 표시한다.
- 등급 미리보기는 저장 없이 적용한다. 테이블 TOP5는 마지막 영업일 주문 건수 순, 동률이면 테이블 번호 순이다. 회원 매출 TOP5는 같은 회원의 반복 주문을 합산하고 마지막 주문 테이블을 표시한다. 비회원은 테이블별로 합산한다.
- 새 서버 테스트 `BT/test_sooyong_sales_insights.py` **41 passed**. KST 경계, 30일 포함/제외 경계, 정확한 합계·객단가·금액대·회전율, 빈 DB, 0원, 회원/비회원, 등급 미리보기 미저장, 새로고침 반영, 인증 401, 잘못된 기준 422를 확인했다. 기존 통계 테스트와 함께 **66 passed**다.
- 새 화면 테스트 `T/test_sooyong_sales_insights.py` **5 passed**. 같은 87건 주문의 서버 계산과 기존 `dashboard_stats.summarize()` 전체 항목 일치, 비회원만 있는 경우, 더미 주문 목록이 비어 있어도 DB 그래프 표시, 하위 화면과 새로고침, 오늘/마지막 영업일 구분, 더미 모드 유지를 검증했다. 관련 화면 테스트 총 **16 passed**다.
- 전체 서버 테스트 **144 passed, 9 skipped**. 전체 화면·통합 테스트 **103 passed, 12 skipped, 7 failed**. 실패는 기존 `T/test_admin_events_page.py`의 룰렛 7개이며, 수정 전 `9b509f6`의 별도 사본에서도 같은 파일의 **7 failed, 11 passed**를 확인했다. 새 skip이나 테스트 삭제는 없다. 초기 임시 폴더 권한 오류는 권한을 확보해 재실행하여 해소했다. 전체 테스트 통과 전에는 PR을 보내지 않는다.
- 실제 Supabase는 스키마 초기화 없이 읽기 전용 트랜잭션으로 점검했다. 새 5개 세부 API와 묶음 조회가 모두 200이며, 최근 주문 115건·매출 6,543,200원·오늘 매출 136,400원·테이블 30개를 확인했다. 시간대/요일 매출 합계와 금액대 주문 수 합계가 일치한다. 실제 DB 기록은 변경하지 않았다.
- 화면 캡처는 별도 메모리 DB의 예시 주문 6건으로 촬영했다. `artifacts/sooyong-stats/before.png`는 기존 화면 계산 경로 재현, `after.png`는 DB 집계 전환 후 매출 화면, `tables.png`는 고객·테이블 분석 화면이다. 예시 오늘 매출 145,000원, 최근 30일 매출 251,000원, 최근 평균 객단가 41,833원이다.

---

## 4. 운영 알림 (미구현)

### 4-1. `GET /api/admin/alerts`

**현재 상태**: 화면(`A/dashboard_stats.py customer_care`, `menu_alerts`)이 휴면 고객·품절 메뉴 알림을 직접 계산한다. DB에는 `alerts` 테이블이 있다(`kind` = dormant / soldout / other, `acknowledged_at`).

**목표**: 휴면 고객 수·품절 메뉴 같은 운영 알림 목록을 돌려준다. 방식은 "조회할 때 계산해서 돌려주기"로 시작한다(테이블 저장은 확인(읽음) 기능이 필요할 때 추가).

**테스트 방법**: 새 테스트 — 휴면 기준을 넘긴 회원이 있으면 `kind=dormant` 알림이 나온다 / 품절 메뉴(`menus.is_soldout`)가 있으면 `kind=soldout` / 둘 다 없으면 빈 목록 / 인증 없으면 401.

**중요 이론**: 알림을 "저장해 두는 방식"과 "조회 때 계산하는 방식"의 차이 — 저장은 읽음 처리·이력에 좋고 계산은 항상 최신이고 단순하다. 품절 메뉴 정보는 서준의 `menus`를 **읽기만** 한다.

**흐름**
```
UI(대시보드 · 운영 알림 패널) → A/views/dashboard.py render_operations → (새) repo.alerts
 → GET /admin/api/alerts → B/routers/admin/alerts.py(신규)
 → B/stores/members.py all() + 메뉴 품절 조회 → DB(members, menus)
 → B/services/grades.py 로 휴면 판정 → [{kind, title, detail, member_id|menu_id}] → UI 알림 카드
```

**상세 설명 / TODO**

- [ ] `B/routers/admin/alerts.py`(신규)와 등록(성호의 선작업 PR에서 빈 틀로 등록됨. 아직이면 `B/routers/admin/__init__.py`에 한 줄 추가).
- [ ] 메뉴 품절 조회는 서준의 `shop.menus()`를 호출한다(서준 구현 전에는 품절 알림 항목을 비워 두고 TODO 주석을 남긴다).
