"""FastAPI 서버 호출 공통 함수."""

import os

import httpx

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def get(path: str, token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.get(f"{API_URL}{path}", headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()
