# 정식 구현 계획: QR 로그인 · SENS 문자 발송

더미(Streamlit 안에서만 동작)로 화면 흐름과 규칙을 확인했다. 이 문서는 더미를 정식 기능으로 바꾸는 기준이다.

## 0. 더미에서 확인된 것 / 확인되지 않은 것

| 구분 | 내용 |
|---|---|
| 확인됨 | 스캔 → 승인 → 로그인 상태에 따른 화면 전환, 3분 만료, 일회용 토큰, 로그인 후 룰렛 1회 추가 |
| 확인됨 | SMS/LMS 구분, 광고 문구 자동 추가, 월 한도 차단, 야간 차단, 수신 동의·수신거부 필터, 발송 내역 |
| 확인 안 됨 | 실제 휴대폰 스캔, 카카오 로그인, 서버↔태블릿 실시간 연결(WebSocket), 실제 문자 수신 |
| 알려진 한계 | user/admin 앱은 별도 프로세스라 데이터를 공유하지 않음 → 백엔드/DB로 해결 |

## 1. QR 로그인

### 흐름
```
태블릿 ──POST /api/auth/qr──────────────▶ 서버: 일회용 토큰 발급(만료 180초)
태블릿 ◀─{token, qr_url, expires_in}────
태블릿 ──WS /api/auth/ws/{token}────────▶ 서버: 연결 유지, 이벤트 대기
휴대폰: QR 스캔 → GET {qr_url} ─────────▶ 서버: scanned 로 변경 → 카카오 인증 페이지로 302
휴대폰: 카카오 로그인 → /api/auth/kakao/callback?code&state
                                         서버: 토큰 교환 → 회원 조회/생성 → logged_in
태블릿 ◀─WS {"event":"logged_in","member":{...},"access_token":"..."}
```

### API 계약 (✅ 구현됨: `backend/app/routers/auth.py`, 테스트 `backend/tests/test_auth.py`)
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/api/auth/qr` | body `{table_no}` → `{token, secret, qr_url, expires_in}` |
| GET | `/api/auth/qr/{secret}` | WS 대체 폴링 → `{status}`. 로그인 완료 시 결과(JWT)를 **한 번만** 반환 |
| GET | `/api/auth/kakao/start?token=` | QR 주소. 스캔 처리 후 카카오(키 없으면 모의 화면)로 302. 만료·사용된 QR은 410 |
| GET | `/api/auth/kakao/callback` | 카카오 콜백. 회원 가입/갱신, JWT 발급, 태블릿에 알림 |
| WS | `/api/auth/ws/{secret}` | 이벤트 `status` → `scanned` → `logged_in`(member, access_token) 또는 `expired` |
| GET/PATCH | `/api/members/me` | JWT 필요. 휴대폰 번호(직접 입력)·마케팅 수신 동의 |

- **token / secret 분리**: QR에는 `token`만 들어간다. 로그인 결과는 태블릿만 아는 `secret`으로만 받을 수 있어, QR을 찍은 제3자가 결과를 가로챌 수 없다.
- **모의 모드**: `KAKAO_REST_API_KEY` 가 비어 있으면 `/api/auth/kakao/mock` 의 간단한 로그인 화면을 쓴다. 키를 넣으면 자동으로 실제 카카오 호출로 바뀌고 모의 화면은 404가 된다.
- 운영 전 `JWT_SECRET` 을 반드시 바꿀 것 (기본값 `change-me`).

### 규칙 (더미에서 검증한 것을 그대로 이식)
- 상태 전이: `waiting → scanned → logged_in`, 또는 `expired`. 되돌리기 없음.
- 토큰은 일회용. 승인된 토큰·만료된 토큰은 재사용 불가 (`user/login_demo.py` 와 `user/test_login.py` 가 기준 명세).
- `state` 파라미터로 CSRF 방지: 콜백의 state 가 발급한 토큰과 일치해야 함.
- 로그인 완료 시 JWT 발급, 태블릿 세션에 저장. 만료·로그아웃 정책은 별도 정의.

### 더미에서 교체할 지점
| 더미 | 정식 |
|---|---|
| `user/login_demo.py` (메모리 상태) | `backend/app/stores/login_sessions.py` (+ 이후 Redis 교체 가능한 인터페이스) |
| `login_action("scan"/"approve")` 버튼 | 휴대폰이 부르는 `/kakao/start`, `/kakao/callback` |
| `login_demo_panel` 2초 폴링 fragment | WebSocket 수신 (Streamlit은 폴링 유지 + 서버 WS 병행 권장) |
| `qr_png()` 가짜 QR | `qrcode` 라이브러리로 `qr_url` 인코딩 |
| 고정 닉네임 `카카오` | 카카오 프로필(닉네임) |

### 회원 테이블 `members`
`id, kakao_id(unique), nickname, phone, gender, birthday, mbti, marketing_consent(bool), marketing_consent_at, opted_out(bool), visit_count, last_visit_at, created_at`

## 2. 문자 발송 (SENS)

### API 계약
| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/admin/api/marketing/sms/preview` | body `{grades[], body, send_at?}` → `{type, bytes, targets, remaining, problems[]}` |
| POST | `/admin/api/marketing/sms/send` | preview 와 동일한 검사 후 발송. 응답 `{request_id, count}` |
| GET | `/admin/api/marketing/sms/usage` | 이번 달 SMS/LMS 사용량·한도 |
| GET | `/admin/api/marketing/sms/logs` | 발송 내역 |
| POST | `/api/members/me/opt-out` | 수신거부 (손님/링크 용) |

### 규칙 (`admin/sens_demo.py` 와 `admin/test_admin.py::SensDemoTests` 가 기준 명세)
- 90바이트 이하 SMS, 초과 LMS (한글 2바이트).
- 본문 앞 `(광고)업체명`, 끝 무료수신거부 안내 자동 삽입.
- 수신 동의 + 수신거부 아님인 회원만. 야간(21~08시) 차단. 월 한도 초과 시 차단.
- 한도 값은 설정(`SMS_MONTHLY_LIMIT`, `LMS_MONTHLY_LIMIT`)으로 이동 — 더미의 50/10은 가정값.
- `SMS_DRY_RUN=true` 이면 SENS 를 호출하지 않고 로그만 기록 (실제 키 없이 전체 흐름 테스트 가능).

### SENS 호출 (v2)
- `POST https://sens.apigw.ntruss.com/sms/v2/services/{serviceId}/messages`
- 헤더 `x-ncp-apigw-timestamp`, `x-ncp-iam-access-key`, `x-ncp-apigw-signature-v2` (HMAC-SHA256: `POST {uri}\n{timestamp}\n{accessKey}`)
- body `{type: SMS|LMS, from, content, messages:[{to}]}` — 한 번에 최대 건수 제한은 호출 전 콘솔 문서로 확인.

### 테이블
`sms_logs(id, request_id, type, content, target_count, status, error, created_at)`, 월 사용량은 `sms_logs` 집계.

## 3. 진행 현황 (갱신: 2026-10-12)

범례: ✅ 완료 · ⏳ 남음(Claude가 구현) · 🙋 당신이 해야 함

### 3-1. QR 로그인
- ✅ 로그인 세션 저장소 (일회용, 3분 만료, token/secret 분리), `/api/auth/*` REST + `WS /api/auth/ws/{secret}` + 폴링
- ✅ 카카오 클라이언트 (키 없으면 모의 모드, 키 있으면 실제 호출 코드), 회원 저장소(SQLite), JWT, `/api/members/me`
- ✅ **[user] 서버 연동**: 실제 QR 이미지(`qrcode`), 2초 폴링으로 로그인 감지, 만료 시 QR 새로고침, `?table=번호`로 테이블 지정
- ✅ **[user] 로그인 후 화면**: 닉네임 표시, 룰렛 한 번 더, 휴대폰 번호·출생연도·성별·마케팅 수신 동의 입력, 문자 수신거부 버튼
- ✅ **룰렛 화면 흐름**: 비로그인 START → 로그인 팝업(QR), 로그인 후 START → 룰렛, 이미 돌린 뒤 START → 다른 회원 로그인 팝업(회원당 1회), 비회원 주문/회원 주문 버튼, 로그인한 회원이 하단에 누적 표시 (화면만, 서버 저장 없음)
- ✅ 더미 시뮬레이션(`login_demo.py`) 제거. 서버가 없으면 QR 로그인만 꺼지고 주문 화면은 그대로 동작
- ✅ 테스트: 백엔드 `backend/tests/test_auth.py`, 통합 `tests/test_qr_login_e2e.py`, 실제 서버 두 개 + 브라우저에서 화면의 QR을 디코딩해 스캔을 흉내 내는 확인까지 완료
- ✅ 운영 모드(`APP_ENV=prod`)에서 기본 비밀값(`change-me`)이면 서버 기동 차단
- ⏳ [백엔드] 로그인 세션 Redis 교체 (여러 프로세스로 운영할 때만 필요)
- ⏳ [백엔드] 로그아웃/JWT 만료 정책 정의
- ⏳ 휴대폰 번호를 직접 입력 대신 카카오 수집으로 바꾸려면 비즈 앱 심사 후 `kakao.py` 수정

### 3-2. 문자 발송 (SENS)
- ✅ 발송 규칙: SMS/LMS 분기, `(광고)` 표기·수신거부 문구 자동 추가, 월 한도, 야간 차단, 수신 동의·번호·수신거부 필터 (`backend/app/services/sens.py`)
- ✅ SENS 호출: v2 서명(HMAC-SHA256), `contentType=AD`, 100명 단위 분할, 실패 시 `failed` 로그. `SMS_DRY_RUN=true`(기본)이면 호출 없이 기록만
- ✅ 발송 로그 `sms_logs`와 월 사용량 집계 (실패는 한도에서 제외)
- ✅ API: `/admin/api/marketing/sms/{preview,send,usage,logs}`, `/admin/api/members/{id}/opt-out`, `/api/members/me/opt-out`
- ✅ **[admin] 마케팅 화면 API 연동** (관리자 토큰 로그인, 사용량·미리보기·발송·수신거부·내역). 더미 `sens_demo.py` 제거
- ✅ 테스트: `backend/tests/test_sms.py`(SENS 호출은 MockTransport), 통합 `tests/test_sms_admin_e2e.py`
- ⏳ SENS 1회 호출당 수신자 수 상한(현재 100)을 콘솔 문서로 확인

### 3-2b. AI 질문 (회의록 2.4) — 더미 데이터 화면
- ✅ 메뉴 화면 왼쪽 위 **[💬 AI 질문]** 버튼 → 한 화면에 질문 하나, 큰 선택 카드, 선택하면 바로 다음 질문 (진행 바·이전·닫기)
- ✅ 질문 8개: 배고픔 → 스트레스 → 인원수 → 성비 → 원하는 종류 → 맵기 → 방문 의도 → 예산 (`user/ai_quiz_data.py`, 더미)
- ✅ 결과: 답변 요약, 자동 반영(시간대·날씨), 추천 조합 최대 3개 + 이유 + 담기. 날씨는 더미(`?weather=rain` 등으로 바꿔 보기)
- ✅ 추천 로직 확장: 맵기 필터 오류 수정, 종류·방문 의도·성비·배고픔·스트레스·시간대·날씨 반영, 사장님 가중치 입력 자리(`weight`), 세트 불가·삭제·품절 메뉴 제외
- ⏳ 질문 목록·선택지를 서버/관리자 설정으로 옮기기 (노출 조건 정의 필요), 날씨 API 연동, 회원 정보(MBTI·선호 등)로 일부 질문 건너뛰기
- ⏳ 추천 노출·선택 기록(적중률 계산)과 백엔드 연결, 주종 질문 추가 여부 결정 (지금은 맥주 고정)

### 3-3. 앞서 분석에서 나온 user 페이지 수정 사항 (아직 미수정)
- ✅ 맵기 필터 오류 수정 ("맵지 않게"인데 "매콤한 골뱅이 한 상"이 추천되던 문제)
- ⏳ `requirements.txt`의 streamlit 최소 버전을 1.65로 상향
- ⏳ `.streamlit/config.toml`을 저장소 루트에서 실행해도 적용되게 이동 (user·admin 공통)
- ⏳ 주문 시각 시간대를 한국(Asia/Seoul)으로
- ✅ 지점명 홍대점 반영 (`user/menu_data.py`, 백엔드 `STORE_BRANCH`)
- ⏳ 메뉴·주문·직원 호출을 백엔드 API와 연결 (`shared/api.py` 사용), 관리자와 데이터 공유
- ⏳ 추천에 사장님 가중치·날씨·시간대 반영, 추천 노출/적중 기록
- ⏳ HTML 이스케이프 일관화, 사용하지 않는 `PROMOS` 정리

## 4. 당신이 해야 할 일 🙋

### 지금 정하면 되는 것
- [x] 지점명: **홍대점**으로 확정, 반영 완료
- [ ] 휴대폰 번호: 카카오 비즈 앱 심사로 받을지, 직접 입력으로 갈지 (현재 코드는 직접 입력 기준)

### 카카오 (로그인 실기기 검증 전까지)
- [ ] developers.kakao.com 앱 생성, REST API 키 발급
- [ ] 카카오 로그인 활성화, Redirect URI 등록 (`{PUBLIC_BASE_URL}/api/auth/kakao/callback`, 개발·운영 각각)
- [ ] 동의항목 설정 (닉네임·성별·생일). 휴대폰 번호는 비즈 앱 심사가 필요함
- [ ] 휴대폰이 접속할 수 있는 서버 주소 확보 (같은 와이파이의 PC 주소, 또는 도메인+HTTPS/터널) → `PUBLIC_BASE_URL`
- [ ] 키를 `backend/.env`에만 입력 (저장소·채팅에 올리지 말 것)

### 네이버 클라우드 SENS (실제 발송 전까지)
- [ ] 네이버 클라우드 가입·결제수단 등록, SENS 프로젝트 생성
- [ ] 서비스 ID, Access Key, Secret Key 발급 → `.env`
- [ ] 발신번호 등록·승인 (통신사 인증, 서류 필요할 수 있음)
- [ ] 무료수신거부 번호 방식 확인 → `SENS_OPT_OUT_NUMBER`
- [ ] 현재 무료 제공량·요금 확인 (한도 값 `SMS_MONTHLY_LIMIT`, `LMS_MONTHLY_LIMIT` 조정)

### 법무·정책
- [ ] 개인정보 처리방침, 이용약관
- [ ] 마케팅 수신 동의 문구 (야간 발송 동의 포함)
- [ ] 고객 등급 분류 기준 확정 (현재는 방문 2회/5회/60일의 임시값), AI 추천 적중률 계산 기준 확정

## 5. 실기기 검증 체크리스트 (더미로는 검증 불가) 🙋
- [ ] 휴대폰 카메라로 태블릿 QR 스캔 → (모의 또는 실제) 카카오 로그인 → 태블릿 화면 자동 전환
- [ ] 로그인 중 QR 만료, 같은 QR 재스캔 시 거부
- [ ] 실제 카카오 계정으로 로그인, 닉네임이 화면에 표시
- [ ] 본인 번호로 SMS·LMS 수신, `(광고)` 표기·수신거부 안내 확인
- [ ] 수신거부 후 재발송 시 제외
- [ ] 월 한도 도달 시 차단

## 6. 다음 순서
1. 🙋 같은 와이파이 휴대폰으로 **모의 모드** 실기기 확인 (`PUBLIC_BASE_URL=http://서버PC주소:8000`, README 참고)
2. 🙋 카카오·SENS 키 준비 → `.env`에 입력 → 실제 모드 전환 후 5장 체크리스트 수행 (SENS는 `SMS_DRY_RUN=false` 로 바꾸기 전에 본인 번호 1건부터)
3. ⏳ 3-3의 user 페이지 수정 사항 (요청 시)
