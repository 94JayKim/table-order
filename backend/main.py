"""uv run fastapi dev main.py 로 실행하는 진입점."""

from app.factory import create_app

app = create_app()
