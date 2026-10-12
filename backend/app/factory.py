"""FastAPI 앱에 CORS와 라우터를 등록한다."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import Settings, get_settings
from app.routers import admin, user


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Table Order API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.include_router(user.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["서버"])
    async def health():
        return {"status": "ok"}

    return app
