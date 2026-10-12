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

## 3. 구현 순서

1. ✅ [백엔드] 회원 저장소(SQLite). 발송 로그 스키마는 5단계에서
2. ✅ [백엔드] 로그인 세션 저장소 + `/api/auth/*` (카카오 mock 어댑터, 키 입력 시 실제 호출)
3. ✅ [백엔드] WebSocket 알림 + 테스트 (만료·재사용·state 불일치·secret 분리)
4. [user] 가짜 QR·시뮬레이션 패널 제거 → API 연동, 로그인 상태 연결
5. [백엔드] SENS 서비스(`SMS_DRY_RUN=true` 기본) + `/admin/api/marketing/*` + 테스트
6. [admin] 마케팅·고객 화면을 API 연동으로 교체 (더미 `dummy_data` 고객 제거)
7. 실제 키 투입 후 실기기 검증 (아래 체크리스트)

## 4. 사용자(당신)가 준비할 것
- [ ] 카카오 개발자 앱: REST API 키, Redirect URI(개발/운영), 동의항목(닉네임·성별·생일). 휴대폰 번호는 비즈 앱 심사 필요 → 안 되면 로그인 직후 직접 입력
- [ ] 공개 접속 주소(도메인+HTTPS 또는 터널) → `PUBLIC_BASE_URL`
- [ ] 네이버 클라우드 가입·결제수단, SENS 프로젝트, 서비스 ID, Access/Secret Key
- [ ] 발신번호 등록·승인, 무료수신거부 번호 방식 확인
- [ ] 개인정보 처리방침, 마케팅 수신 동의 문구(야간 발송 동의 포함)
- [ ] SENS 현재 무료 제공량·요금 확인
- [ ] 키는 `backend/.env` 에만 입력 (저장소·채팅에 올리지 말 것)

## 5. 실기기 검증 체크리스트 (더미로는 검증 불가)
- [ ] 휴대폰 카메라로 태블릿 QR 스캔 → 카카오 로그인 → 태블릿 화면 자동 전환
- [ ] 로그인 중 QR 만료, 같은 QR 재스캔 시 거부
- [ ] 본인 번호로 SMS·LMS 수신, `(광고)` 표기·수신거부 안내 확인
- [ ] 수신거부 후 재발송 시 제외
- [ ] 월 한도 도달 시 차단
