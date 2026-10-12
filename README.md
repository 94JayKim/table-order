# Table Order

FastAPI 서버 + 사용자 페이지 + 관리자 페이지를 한 저장소에서 관리하는 모노레포입니다.

```
backend/   FastAPI 서버 (app factory 구조: core / routers / services / stores)
user/      사용자(손님) Streamlit 페이지
admin/     관리자 Streamlit 페이지
shared/    두 페이지가 같이 쓰는 API 호출 코드
```

## 실행

```bash
# 서버 (http://127.0.0.1:8000/docs)
cd backend
cp .env.example .env
uv sync
uv run fastapi dev main.py

# 페이지 (저장소 루트에서, 서버가 켜져 있어야 QR 로그인·문자 발송이 동작)
pip install -r requirements.txt
streamlit run user/app.py --server.port 8501    # 사용자 (?table=12 로 테이블 지정)
streamlit run admin/app.py --server.port 8502   # 관리자 (로그인: backend/.env 의 ADMIN_TOKEN)
```

- 휴대폰으로 QR 로그인을 시험하려면 `backend/.env` 의 `PUBLIC_BASE_URL` 을 서버 PC 주소(예: `http://192.168.0.10:8000`)로 두고 `--host 0.0.0.0` 으로 실행하세요. 카카오 키가 없으면 모의 로그인 화면이 열립니다.
- 문자 발송은 `SMS_DRY_RUN=true`(기본)이면 실제 전송 없이 기록만 남깁니다.
- 자세한 계획과 체크리스트: `docs/PRODUCTION_PLAN.md`

## 테스트

```bash
(cd backend && python -m pytest)          # 백엔드
python -m pytest tests                    # user·admin ↔ 백엔드 통합
(cd user && python -m unittest test_cart test_recommendations)
```

## 규칙

- API 경로: 사용자용 `/api/...`, 관리자용 `/admin/api/...`
- CORS 허용 주소는 `backend/.env`의 `CORS_ORIGINS`에서 관리
