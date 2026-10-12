"""환경 변수에서 설정을 읽는다."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:8502"]
    admin_token: str = "change-me"

    # QR 로그인 / 카카오 (docs/PRODUCTION_PLAN.md 1장)
    public_base_url: str = "http://localhost:8000"  # 휴대폰이 접속할 서버 주소 (QR에 들어감)
    kakao_rest_api_key: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/api/auth/kakao/callback"
    jwt_secret: str = "change-me"
    login_ttl_seconds: int = 180
    jwt_expire_minutes: int = 720

    # 문자 발송 / 네이버 클라우드 SENS (docs/PRODUCTION_PLAN.md 2장)
    sens_service_id: str = ""
    sens_access_key: str = ""
    sens_secret_key: str = ""
    sens_sender_number: str = ""  # SENS에 등록·승인된 발신번호
    sens_opt_out_number: str = ""  # 광고 문자 하단의 무료수신거부 번호
    sms_monthly_limit: int = 50
    lms_monthly_limit: int = 10
    sms_dry_run: bool = True  # True면 SENS를 호출하지 않고 로그만 남긴다


@lru_cache
def get_settings() -> Settings:
    return Settings()
